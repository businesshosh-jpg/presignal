#!/usr/bin/env python3
"""Freeze only Round 2 prompt authority; reject an ungoverned cutoff offset."""
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

from automation import presignal_v21_event_path_contract_v1_1 as contract
from automation import run_presignal_v21_single_event_path_pair_v1_1 as pair_runner


BASE = ROOT / "outputs" / "presignal_v21_full_round_1_forecast_execution"
PROTOCOL_PATH = BASE / "PPHB-R2-CONFIRMATORY-PROSPECTIVE-PROTOCOL-20260804T080000Z" / "round_2_protocol.json"
ENVELOPE_PATH = BASE / "PPHB-R2-EXECUTION-ENVELOPE-PREPARATION-20260803T090000Z" / "execution_envelope.json"
ARTIFACT_ID = "PPHB-R2-PROMPT-CUTOFF-AUTHORITY-RECONCILIATION-20260804T011500Z"
DEFAULT_OUTPUT_DIR = BASE / ARTIFACT_ID


class AuthorityError(ValueError):
    """The governing sources do not uniquely authorize the requested binding."""


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def prompt_authority() -> dict[str, Any]:
    source = pair_runner.prompt_instruction_text(
        include_future_no_signal_confidence_clarification=True,
    )
    fingerprint = pair_runner.prompt_instruction_fingerprint(
        include_future_no_signal_confidence_clarification=True,
    )
    if fingerprint != "sha256:2515e6c09742e58507efe8d9196ba58473c01f2d5bb9e8b5405405088d323a77":
        raise AuthorityError("FUTURE_PROMPT_FINGERPRINT_CONFLICT")
    if fingerprint != digest(source):
        raise AuthorityError("PROMPT_SOURCE_FINGERPRINT_CONFLICT")
    common = {
        "prompt_id": "PPHB-V2.1-EVENT-PATH-FUTURE-NO-SIGNAL-CONFIDENCE-EXPLICIT-V1",
        "prompt_version": pair_runner.FUTURE_NO_SIGNAL_PROMPT_VERSION,
        "instruction_source": "automation/run_presignal_v21_single_event_path_pair_v1_1.py::prompt_instruction_text(include_future_no_signal_confidence_clarification=True)",
        "complete_prompt_source": source,
        "prompt_instruction_fingerprint": fingerprint,
        "forecast_output_contract": {
            "contract_version": contract.CONTRACT_VERSION,
            "schema_version": contract.SCHEMA_VERSION,
            "response_contract_version": contract.CONTRACT_VERSION,
            "required_horizons_minutes": list(contract.HORIZONS),
            "directions": sorted(contract.DIRECTIONS),
            "flat_rule": "FLAT requires zero-to-zero pip bounds under the frozen instruction and the canonical contract tie rule.",
            "no_signal_rule": "NO_SIGNAL is permitted only when no defensible directional hypothesis is available; confidence remains numeric from 0 to 1.",
            "immediate_impulse": "Fixed T through T+120 seconds sidecar; omission of immediate_impulse_window_seconds is permitted because the system inserts 120.",
        },
        "provider_model_compatibility": [
            {"provider": "Anthropic", "model": "claude-haiku-4-5"},
            {"provider": "Gemini", "model": "gemini-2.5-flash-lite"},
            {"provider": "OpenAI", "model": "gpt-4o-mini-2024-07-18"},
        ],
        "lineage": {
            "migration": "PPHB-R1-FORECAST-FUTURE-NO-SIGNAL-PROMPT-MIGRATION-20260801T130644Z-2bcc88d1ba5e",
            "rule": "The accepted migration applies this future prompt to unexecuted Pack A batch A004 onward and all Pack E calls; Round 2 is prospective and has no executed prior calls.",
        },
    }
    pack_construction = {
        "input_constructor": "automation/run_presignal_v21_single_event_path_pair_v1_1.py::arm_context",
        "allowed_pack_specific_context_fields": sorted(pair_runner.ALLOWED_PROMPT_DIFFERENCES),
        "pack_a": {
            **common,
            "pack": "A",
            "pack_role": "baseline",
            "canonical_information_arm": "BASELINE",
            "pack_input_rule": "information_pack and information_pack_fingerprint are null.",
        },
        "pack_e": {
            **common,
            "pack": "E",
            "pack_role": "experimental",
            "canonical_information_arm": "FULL_CONTEXT",
            "pack_input_rule": "information_pack and information_pack_fingerprint bind the frozen shared_market_state_pack and pack_fingerprint.",
        },
        "proof": "The static instruction is intentionally identical. arm_context and prompt_diff preserve Pack distinction exclusively through information_arm, information_pack, and information_pack_fingerprint; call identities separately bind Pack and Pack-input fingerprint.",
    }
    return {
        "decision": "ROUND_2_PACK_PROMPT_AUTHORITY_FROZEN",
        "prompt_authority": pack_construction,
        "validation": {
            "single_future_prompt_version": pair_runner.FUTURE_NO_SIGNAL_PROMPT_VERSION,
            "single_future_prompt_fingerprint": fingerprint,
            "pack_a_and_pack_e_static_instruction_equal": True,
            "pack_input_distinction_preserved": True,
            "no_external_access": True,
        },
    }


def cutoff_authority() -> dict[str, Any]:
    protocol = read_json(PROTOCOL_PATH)
    envelope = read_json(ENVELOPE_PATH)
    rules = [
        protocol["prospective_boundary"]["release_and_cutoff_rule"],
        envelope["prompt_and_cutoff_authority"]["cutoff_rule"],
    ]
    if len(set(rules)) != 1:
        raise AuthorityError("CUTOFF_ORDERING_AUTHORITY_CONFLICT")
    return {
        "decision": "ROUND_2_PROSPECTIVE_CUTOFF_AUTHORITY_BLOCKED",
        "accepted_ordering_rule": rules[0],
        "missing_required_numeric_authority": [
            "cutoff offset relative to release",
            "minimum lead time",
            "clock authority",
            "dispatch-permitted window start",
            "revised-release-time recalculation rule",
        ],
        "reason": "The protocol and envelope govern only the strict timestamp ordering. They do not select a numeric offset or the required operational timing semantics, and fixture or historical timestamps cannot be promoted into authority.",
        "fail_closed_effect": "No Event eligibility classification, Episode admission, Slice manifest, forecast-call inventory, or provider-dispatch authorization may be created.",
        "no_external_access": True,
    }


def build_evidence() -> dict[str, Any]:
    prompts = prompt_authority()
    cutoff = cutoff_authority()
    result = {
        "artifact_id": ARTIFACT_ID,
        "schema_version": "1.0.0",
        "protocol_binding": {
            "protocol_id": "PPHB-R2-CONFIRMATORY-PROSPECTIVE-PROTOCOL-20260804T080000Z",
            "protocol_fingerprint": "sha256:d417e4c76d3d38d471dbc76cbf361be4a28dac1b615ecccdc8aa18c37262362f",
        },
        "envelope_binding": {
            "envelope_id": "PPHB-R2-EXECUTION-ENVELOPE-20260803T090000Z",
            "envelope_fingerprint": "sha256:3fe721eee816e48a5eca00c50cbcbc397bec6258d60bdfc7857e8169869efdd0",
        },
        "event_snapshot_binding": {
            "snapshot_id": "PPHB-R2-CURRENT-EVENT-SNAPSHOT-20260803T151000Z",
            "snapshot_fingerprint": "sha256:afab082d51abdd725b7c1a802c3391673de91e65c2b964b5cd31a29f3475b6d9",
            "not_read_or_admitted": True,
        },
        "prompt": prompts,
        "cutoff": cutoff,
        "downstream_decisions": {
            "manifest": "ROUND_2_FIRST_ROLLING_SLICE_MANIFEST_BLOCKED",
            "dispatch_authorization": "ROUND_2_FIRST_SLICE_EXACT_DISPATCH_AUTHORIZATION_NOT_READY",
            "reason": "A numeric prospective cutoff is required before per-Episode admission and exact provider-call identity construction.",
        },
        "activity": {
            "provider_calls": 0,
            "google_access": 0,
            "google_writes": 0,
            "market_data_access": 0,
            "outcome_activity": 0,
            "evaluation_activity": 0,
            "retries": 0,
        },
    }
    result["artifact_fingerprint"] = digest(result)
    return result


def freeze(output_dir: Path = DEFAULT_OUTPUT_DIR) -> dict[str, Any]:
    if output_dir.exists():
        raise AuthorityError("PROMPT_CUTOFF_AUTHORITY_ARTIFACT_ALREADY_EXISTS")
    evidence = build_evidence()
    output_dir.mkdir(parents=True)
    (output_dir / "prompt_cutoff_authority_reconciliation.json").write_text(
        json.dumps(evidence, indent=2, sort_keys=True) + "\n"
    )
    return evidence


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()
    print(json.dumps(freeze(args.output_dir), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
