#!/usr/bin/env python3
"""Prepare a local-only Round 2 envelope and fail closed without live Episodes."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from automation import freeze_presignal_v21_round_2_protocol as protocol_builder


BASE = ROOT / "outputs" / "presignal_v21_full_round_1_forecast_execution"
PROTOCOL_PATH = BASE / "PPHB-R2-CONFIRMATORY-PROSPECTIVE-PROTOCOL-20260804T080000Z" / "round_2_protocol.json"
OUTPUT_DIR = BASE / "PPHB-R2-EXECUTION-ENVELOPE-PREPARATION-20260803T090000Z"
ENVELOPE_ID = "PPHB-R2-EXECUTION-ENVELOPE-20260803T090000Z"


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def file_digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def load_protocol(path: Path) -> dict[str, Any]:
    protocol = json.loads(path.read_text())
    protocol_builder.validate_protocol(protocol)
    if protocol.get("protocol_id") != "PPHB-R2-CONFIRMATORY-PROSPECTIVE-PROTOCOL-20260804T080000Z":
        raise ValueError("ROUND_2_PROTOCOL_IDENTITY_CONFLICT")
    if protocol.get("protocol_fingerprint") != "sha256:d417e4c76d3d38d471dbc76cbf361be4a28dac1b615ecccdc8aa18c37262362f":
        raise ValueError("ROUND_2_PROTOCOL_FINGERPRINT_CONFLICT")
    return protocol


def build_envelope(protocol: dict[str, Any]) -> dict[str, Any]:
    return {
        "envelope_id": ENVELOPE_ID,
        "envelope_schema_version": "1.0.0",
        "envelope_status": "FROZEN_INACTIVE_NO_PROVIDER_AUTHORITY",
        "timestamp_semantics": "Deterministic artifact naming metadata only; not an issuance or validity boundary.",
        "decision": "ROUND_2_EXECUTION_ENVELOPE_FROZEN",
        "protocol_binding": {"protocol_id": protocol["protocol_id"], "protocol_fingerprint": protocol["protocol_fingerprint"]},
        "round_2_identity": "PRESIGNAL-R2-CONFIRMATORY-PACK-A-VS-PACK-E",
        "prospective_start_condition": "Accepted protocol, authoritative future Episode source, first Slice manifest, and separate forecast-dispatch authorization must all be frozen before provider dispatch.",
        "population_limits": {
            "maximum_admitted_episodes": 144,
            "target_admitted_episodes": 120,
            "target_common_paired_scoreable_observations": 240,
            "minimum_common_paired_scoreable_observations": 200,
            "maximum_episodes_per_slice": 48,
        },
        "selection_and_ordering": "Select unique future Episodes in authoritative release order, then exact release timestamp and Episode identity, excluding all Round 1 identities and any unresolved or reused identity.",
        "identity_construction": {
            "forecast": "Existing canonical v2.1 call identity bound to Slice, Episode, Pack, provider, model, cutoff, prompt version/fingerprint, release timestamp, instrument, horizons, and append-only lineage.",
            "outcome": "Existing presignal_event_path_contract_v1_1 / schema 2.1.1 identity bound to Episode, USD/JPY, release timestamp, windows, source authority, and append-only lineage.",
        },
        "provider_model_allocation": {
            "routes": protocol["provider_model_control"]["permitted_provider_models"],
            "rule": protocol["provider_model_control"]["allocation_rule"],
            "pack_pairing": "One Pack A and one Pack E call per admitted Episode and provider/model route, with shared cutoff and release identity.",
        },
        "prompt_and_cutoff_authority": {
            "prompt_version": "Frozen canonical prospective v2.1 prompt version from the accepted forecast contract and first Slice manifest.",
            "prompt_fingerprint": "Must be recorded per call before dispatch; any mismatch is a governance stop.",
            "cutoff_rule": protocol["prospective_boundary"]["release_and_cutoff_rule"],
            "historical_leakage": protocol["prospective_boundary"]["historical_leakage_prevention"],
        },
        "append_only_requirements": ["manifest", "authorization", "lease and reservation records", "raw provider output", "request/response metadata", "strict validation result", "resume evidence", "blocker evidence"],
        "duplicate_and_resume": {
            "duplicate_dispatch_prevention": "Reserve each exact call identity before client construction or dispatch; an accepted response is never dispatched again.",
            "resume": "Resume only from accepted append-only reservation and response evidence; ambiguous post-dispatch state stops and requires governance.",
        },
        "completion_conditions": ["all authorized Slice manifests complete", "all forecast and Outcome identities reconciled", "no duplicate or unresolved identity", "target/minimum common-pair rule resolved at final lock", "separately authorized final Round 2 inference completed"],
        "mandatory_governance_stops": protocol["mandatory_governance_stops"],
        "not_authorized_by_envelope": ["provider calls", "Google access or writes", "market-data access", "Outcome collection or attachment", "evaluation", "retries", "manifest selection without an authoritative prospective source"],
    }


def build_blocked_slice_evidence(protocol: dict[str, Any], envelope: dict[str, Any]) -> dict[str, Any]:
    return {
        "artifact_status": "FIRST_SLICE_MANIFEST_BLOCKED_NOT_FROZEN",
        "decision": "ROUND_2_FIRST_PROSPECTIVE_SLICE_MANIFEST_BLOCKED",
        "protocol_binding": {"protocol_id": protocol["protocol_id"], "protocol_fingerprint": protocol["protocol_fingerprint"]},
        "envelope_binding": {"envelope_id": envelope["envelope_id"], "envelope_fingerprint": digest(envelope)},
        "selection_rule": envelope["selection_and_ordering"],
        "eligible_episode_count": 0,
        "selected_episode_count": 0,
        "frozen_forecast_call_count": 0,
        "pack_a_count": 0,
        "pack_e_count": 0,
        "complete_pairs": 0,
        "exclusions": {
            "round_1_historical_episodes": "All accepted real Episode manifests are May-July 2024 Round 1 identities and are excluded.",
            "synthetic_prospective_fixtures": "PSS dry-run records such as EP_EVENT_PROSPECTIVE use placeholder 2030 timestamps and are explicitly non-authoritative test fixtures; they cannot populate a live Slice.",
        },
        "source_authority_finding": "No authoritative current prospective Episode registry, release schedule, or future event source is present in repository evidence.",
        "unresolved_conflict": "PROSPECTIVE_EPISODE_SOURCE_AUTHORITY_MISSING",
        "external_access": 0,
    }


def build_dispatch_inputs(protocol: dict[str, Any], envelope: dict[str, Any], blocker: dict[str, Any]) -> dict[str, Any]:
    return {
        "artifact_status": "DISPATCH_AUTHORIZATION_INPUTS_NOT_READY",
        "decision": "ROUND_2_FIRST_SLICE_DISPATCH_AUTHORIZATION_INPUTS_NOT_READY",
        "protocol_binding": {"protocol_id": protocol["protocol_id"], "protocol_fingerprint": protocol["protocol_fingerprint"]},
        "envelope_binding": {"envelope_id": envelope["envelope_id"], "envelope_fingerprint": digest(envelope)},
        "manifest_binding": None,
        "exact_forecast_call_identities": [],
        "authorized_provider_model_routes": protocol["provider_model_control"]["permitted_provider_models"],
        "maximum_provider_calls": 0,
        "maximum_calls_per_provider": {"Anthropic": 0, "Gemini": 0, "OpenAI": 0},
        "retry_boundary": 0,
        "transport_path": "Existing canonical provider dispatch path only, once separately authorized.",
        "raw_output_preservation": "Required before parsing or validation.",
        "lease_and_reservation": "Exclusive execution lease and durable per-call reservation are required before dispatch.",
        "remote_state_stop": "Any ambiguous post-dispatch state is remote-state-unknown and stops without retry.",
        "prohibited_operations": ["Outcome access", "market-data access", "Google writes", "evaluation", "contingency calls"],
        "blocking_reference": blocker["unresolved_conflict"],
    }


def freeze(output_dir: Path = OUTPUT_DIR) -> dict[str, Any]:
    if output_dir.exists():
        raise ValueError("ROUND_2_ENVELOPE_ARTIFACT_ALREADY_EXISTS")
    protocol = load_protocol(PROTOCOL_PATH)
    envelope = build_envelope(protocol)
    blocker = build_blocked_slice_evidence(protocol, envelope)
    dispatch = build_dispatch_inputs(protocol, envelope, blocker)
    envelope["envelope_fingerprint"] = digest(envelope)
    blocker["envelope_binding"]["envelope_fingerprint"] = envelope["envelope_fingerprint"]
    dispatch["envelope_binding"]["envelope_fingerprint"] = envelope["envelope_fingerprint"]
    validation = {
        "decision": "ROUND_2_EXECUTION_ENVELOPE_FROZEN",
        "manifest_decision": blocker["decision"],
        "dispatch_decision": dispatch["decision"],
        "protocol_binding_valid": True,
        "prospective_only_selection": True,
        "synthetic_fixture_excluded": True,
        "external_access": 0,
        "provider_calls": 0,
        "google_writes": 0,
        "market_data_access": 0,
        "outcome_activity": 0,
        "metric_calculation": 0,
        "blocking_conflict": blocker["unresolved_conflict"],
    }
    output_dir.mkdir(parents=True)
    files = {
        "execution_envelope.json": envelope,
        "first_slice_population_proof.json": blocker,
        "first_slice_manifest_blocker.json": blocker,
        "forecast_dispatch_authorization_inputs.json": dispatch,
        "preparation_validation.json": validation,
        "preparation_decision.json": {
            "envelope_decision": validation["decision"],
            "manifest_decision": validation["manifest_decision"],
            "dispatch_decision": validation["dispatch_decision"],
            "envelope_id": envelope["envelope_id"],
            "envelope_fingerprint": envelope["envelope_fingerprint"],
            "external_access": 0,
        },
    }
    for name, value in files.items():
        (output_dir / name).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    return validation


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    args = parser.parse_args()
    print(json.dumps(freeze(args.output_dir), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
