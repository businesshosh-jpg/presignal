#!/usr/bin/env python3
"""Fail closed on a Round 2 Pack E source contract absent prospective authority."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from automation import presignal_v21_prospective_lineage_adapter_v1 as adapter

BASE = ROOT / "outputs" / "presignal_v21_full_round_1_forecast_execution"
OUTPUT_DIR = BASE / "PPHB-R2-SHARED-MARKET-STATE-CONTRACT-RECONCILIATION-20260804T025000Z"


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def fingerprint(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def reconcile(output_dir: Path = OUTPUT_DIR) -> dict[str, Any]:
    if output_dir.exists():
        raise RuntimeError("SHARED_MARKET_STATE_RECONCILIATION_ALREADY_EXISTS")
    inventory = adapter.source_inventory()
    pack = next(row for row in inventory if row["stage"] == "PACK")
    deployed = adapter.deployed_interface_manifest()
    if pack["current_deployed_equivalent"] != "NONE" or deployed["function_presence"]["shared_market_state_pack_return_only"]:
        raise RuntimeError("EXPECTED_PROSPECTIVE_SOURCE_AUTHORITY_STATE_CONFLICT")
    evidence = {
        "reconciliation_id": output_dir.name,
        "bindings": {
            "protocol": "PPHB-R2-CONFIRMATORY-PROSPECTIVE-PROTOCOL-20260804T080000Z",
            "envelope": "PPHB-R2-EXECUTION-ENVELOPE-20260803T090000Z",
            "cutoff_amendment": "PPHB-R2-T-MINUS-15-CUTOFF-PROTOCOL-AMENDMENT-20260804T013000Z",
            "prompt_fingerprint": "sha256:2515e6c09742e58507efe8d9196ba58473c01f2d5bb9e8b5405405088d323a77",
        },
        "decisions": {
            "contract": "ROUND_2_SHARED_MARKET_STATE_CONTRACT_BLOCKED",
            "source_authority": "ROUND_2_SHARED_MARKET_STATE_SOURCE_AUTHORITY_CONFLICT",
            "lead_time": "ROUND_2_SHARED_MARKET_STATE_LEAD_TIME_AUTHORITY_BLOCKED",
            "controller": "CONTINUOUS_ROUND_2_PRE_CUTOFF_ORCHESTRATION_BLOCKED",
            "new_slice": "ROUND_2_NEW_SLICE_GOVERNANCE_BLOCKED",
        },
        "canonical_pack_e_schema": {
            "pack_required_fields": ["pack_id", "pack_freeze_id", "session_id", "information_cutoff_ts", "pack_generated_ts", "items", "source_request_run_ids", "source_kind", "pack_fingerprint"],
            "item_required_fields": ["source_timestamp"],
            "item_timestamp_rule": "source_timestamp must be strictly before information_cutoff_ts; forbidden Outcome/evaluation/released-value fields are rejected.",
            "field_inventory_decision": "No canonical prospective market-state field/category list is defined. The historical builder accepts source bundles and mutable sheet state, so field-level source, unit, stale-data, and schema authority cannot be inferred.",
        },
        "source_authority": {
            "historical_source_path": pack["source_path"],
            "historical_entrypoint": pack["entrypoint"],
            "historical_input_schema": pack["input_schema"],
            "current_deployed_equivalent": pack["current_deployed_equivalent"],
            "deployed_return_only_entrypoint": deployed["function_presence"]["shared_market_state_pack_return_only"],
            "reason": "No accepted prospective source route, adapter, schema, authentication path, response authority, or request ceiling exists. Historical replay/sheet inputs cannot be promoted to prospective authority.",
        },
        "timestamp_and_leakage": {
            "required_if_authorized": "item_available_timestamp_utc < Episode forecast cutoff; use authoritative publication/observation time rather than retrieval time where defined.",
            "blocked_without_source_contract": ["observation-vs-publication precedence", "stale-data rule", "missing-data rule", "revised-data rule", "timezone authority", "same-second source behavior"],
            "prohibited": ["post-cutoff observations", "post-release revisions", "Outcome prices", "later market moves", "Round 1 results", "provider-performance data", "historical reconstructed snapshots without availability proof"],
        },
        "lead_time": {
            "known_provider_limits_seconds": {"attention": 180, "information_requests": 180},
            "unknown_component": "shared-market-state source execution ceiling and response/availability bound",
            "admission_deadline": "NOT_FROZEN: maximum prerequisite execution window cannot be derived while a required source is undefined.",
        },
        "slice_001": {"decision": "ROUND_2_SLICE_001_PRE_CUTOFF_PACK_INPUTS_MISSING_NON_REUSABLE", "reused": False},
        "external_activity": {"provider_calls": 0, "google_reads": 0, "google_writes": 0, "market_data_calls": 0, "outcome_activity": 0, "evaluation_activity": 0, "retries": 0},
        "required_next_authority": "Freeze one explicit prospective shared-market-state field inventory and source contract, including each source route, canonical schema, timestamp precedence, exact request identity construction, call ceilings, and bounded completion time before authorizing any acquisition.",
        "recorded_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
    }
    evidence["fingerprint"] = fingerprint({key: value for key, value in evidence.items() if key not in {"recorded_utc", "fingerprint"}})
    output_dir.mkdir(parents=True)
    (output_dir / "shared_market_state_contract_reconciliation.json").write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n")
    return evidence


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR); args = parser.parse_args()
    print(json.dumps(reconcile(args.output_dir), sort_keys=True)); return 0


if __name__ == "__main__":
    raise SystemExit(main())
