#!/usr/bin/env python3
"""Call-free preflight for the exact Round 2 first-Slice dispatch authority."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

BASE = ROOT / "outputs" / "presignal_v21_full_round_1_forecast_execution"
PREP_DIR = BASE / "PPHB-R2-T-MINUS-15-FIRST-SLICE-20260804T013000Z"
OUTPUT_DIR = BASE / "PPHB-R2-FIRST-ROLLING-SLICE-001-DISPATCH-EXECUTION-20260804T020000Z"
AUTHORIZATION_ID = "PPHB-R2-FIRST-ROLLING-SLICE-DISPATCH-AUTHORIZATION-20260804T013000Z"
AUTHORIZATION_FINGERPRINT = "sha256:04bd63ca29550357bbf49161d862291fba7b4aafe4676e1342b1b9cec1c73692"
MANIFEST_ID = "PPHB-R2-FIRST-ROLLING-SLICE-MANIFEST-20260804T013000Z"
MANIFEST_FINGERPRINT = "sha256:4eba0d76f06bc29b3c6360acf1c0d18153c2a0d59ae40e02df995b1aa636342e"
PROMPT_FINGERPRINT = "sha256:2515e6c09742e58507efe8d9196ba58473c01f2d5bb9e8b5405405088d323a77"


class DispatchGovernanceBlocked(RuntimeError):
    pass


def read(name: str) -> Any:
    return json.loads((PREP_DIR / name).read_text())


def validate_frozen_authority() -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    authorization = read("provider_dispatch_authorization.json")
    manifest = read("first_slice_manifest.json")
    calls = read("forecast_call_inventory.json")["calls"]
    if authorization.get("authorization_id") != AUTHORIZATION_ID or authorization.get("fingerprint") != AUTHORIZATION_FINGERPRINT:
        raise DispatchGovernanceBlocked("AUTHORIZATION_BINDING_CONFLICT")
    if manifest.get("manifest_id") != MANIFEST_ID or manifest.get("manifest_fingerprint") != MANIFEST_FINGERPRINT:
        raise DispatchGovernanceBlocked("MANIFEST_BINDING_CONFLICT")
    if len(calls) != 186 or authorization.get("maximum_provider_calls") != 186:
        raise DispatchGovernanceBlocked("CALL_CEILING_CONFLICT")
    if any(call.get("prompt_fingerprint") != PROMPT_FINGERPRINT for call in calls):
        raise DispatchGovernanceBlocked("PROMPT_FINGERPRINT_CONFLICT")
    return authorization, manifest, calls


def preflight(output_dir: Path = OUTPUT_DIR) -> dict[str, Any]:
    if output_dir.exists():
        raise DispatchGovernanceBlocked("EXECUTION_EVIDENCE_ALREADY_EXISTS")
    authorization, manifest, calls = validate_frozen_authority()
    required_materialization = ("pack_input_payload", "pack_input_artifact", "pack_input_path")
    missing = [call["call_id"] for call in calls if not any(key in call for key in required_materialization)]
    if missing:
        decision = "ROUND_2_FIRST_SLICE_FORECAST_EXECUTION_GOVERNANCE_BLOCKED"
        evidence = {
            "execution_run_id": output_dir.name,
            "decision": decision,
            "blocker": "PACK_INPUT_AUTHORITY_MATERIALIZATION_MISSING",
            "reason": "The frozen inventory contains Pack-input fingerprints but no canonical Pack-input payload or immutable input artifact/path. The accepted transport cannot construct the exact provider-visible Pack A/FULL_CONTEXT or Pack E/BASELINE context without inventing scientific inputs.",
            "authorization": {"id": authorization["authorization_id"], "fingerprint": authorization["fingerprint"], "activation": "NOT_ACTIVATED"},
            "manifest": {"id": manifest["manifest_id"], "fingerprint": manifest["manifest_fingerprint"]},
            "cutoff_amendment": {"id": "PPHB-R2-T-MINUS-15-CUTOFF-PROTOCOL-AMENDMENT-20260804T013000Z", "fingerprint": "sha256:a4200c3e5704ea1ba172967847e71d664f63b75d64c013fe2fbaf78ee0290085"},
            "frozen_calls": len(calls),
            "identity_partition": {"GOVERNANCE_BLOCKED_PACK_INPUT_AUTHORITY": sorted(missing), "DISPATCH_AUTHORIZED_PRE_CUTOFF": [], "CUTOFF_PASSED_NOT_AUTHORIZED": [], "ATTEMPTED": [], "VALID": [], "TERMINAL_INVALID": [], "REMOTE_STATE_UNKNOWN": [], "DUPLICATE": []},
            "lease": {"acquired": False, "reason": "Shared scientific-input authority failed before lease/reservation creation."},
            "reservations": {"created": 0},
            "actuals": {"provider_calls": 0, "google_writes": 0, "market_data_calls": 0, "outcome_activity": 0, "evaluation_activity": 0, "retries": 0},
            "required_next_authority": "Materialize and fingerprint the canonical Pack A and Pack E provider-visible inputs, then freeze a replacement single-use dispatch authorization; do not reuse this authorization.",
            "recorded_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        }
        output_dir.mkdir(parents=True)
        (output_dir / "dispatch_governance_blocker.json").write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n")
        return evidence
    raise DispatchGovernanceBlocked("UNEXPECTED_NO_BLOCKER")


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR); args = parser.parse_args()
    print(json.dumps(preflight(args.output_dir), sort_keys=True)); return 0


if __name__ == "__main__":
    raise SystemExit(main())
