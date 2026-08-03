#!/usr/bin/env python3
"""Freeze the supplementary no-external-call evaluation authorization for Slice 003."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "outputs" / "presignal_v21_full_round_1_forecast_execution"
MANIFEST_FP = "sha256:c15ec51effbb6ac5d26a48ead4c28504d0f5fc8e8a157e650726fc2fd1815bd5"
MANIFEST_ID = "PPHB-R1-OUTCOME-COLLECTION-MANIFEST-SLICE-003-20260803T154000Z"
COLLECTION_RUN = "PPHB-R1-OUTCOME-COLLECTION-SLICE-003-20260803T071136Z-fc2fd1815bd5"
REVIEW_ID = "PPHB-R1-SLICE-003-UNAVAILABLE-OUTCOME-GOVERNANCE-REVIEW-20260803T073000Z"
ATTACHMENT_AUTH = "PPHB-R1-SLICE-003-PAIRED-EXCLUSION-ATTACHMENT-AUTHORIZATION-20260803T080000Z"
ATTACHMENT_RUN = "PPHB-R1-OUTCOME-ATTACH-SLICE-003-PAIRED-EXCLUSION-20260803T080000Z-81ea4814a18d"
AUTHORIZATION_ID = "PPHB-R1-SLICE-003-SUPPLEMENTARY-EVALUATION-AUTHORIZATION-20260803T081500Z"


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def fingerprint(value: dict[str, Any]) -> str:
    body = {key: value[key] for key in value if key != "authorization_fingerprint"}
    return "sha256:" + hashlib.sha256(canonical(body).encode()).hexdigest()


def write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def build_authorization(controller_commit: str) -> dict[str, Any]:
    auth = {
        "authorization_id": AUTHORIZATION_ID,
        "authorization_schema_version": "SUPPLEMENTARY_SLICE_EVALUATION_AUTH_V1",
        "authorization_status": "ACTIVE",
        "authorization_mode": "MINIMAL_EVALUATION",
        "slice_id": "SLICE-003",
        "manifest_id": MANIFEST_ID,
        "manifest_fingerprint": MANIFEST_FP,
        "controller_commit": controller_commit,
        "contract_binding": "PPHB-R1-PROSPECTIVE-SLICE-EXECUTION-CONTRACT-20260803T060000Z",
        "collection_run_id": COLLECTION_RUN,
        "governance_review_id": REVIEW_ID,
        "paired_exclusion_attachment_authorization_id": ATTACHMENT_AUTH,
        "attachment_run_id": ATTACHMENT_RUN,
        "evaluation_entrypoint": "automation/evaluate_presignal_v21_outcome_slice_001.py",
        "evaluation_population": {"episodes": 10, "valid_forecasts": 32, "pack_a": 16, "pack_e": 16, "complete_pairs": 16, "unpaired": 0},
        "terminal_invalid_excluded": ["FCL_27720b8b23236b173b96fdee", "FCL_7f0463b134c67757968580e8", "FCL_e07264654e9d3da6f63088a1"],
        "permitted_metrics": ["T+15 directional accuracy", "Immediate Impulse directional accuracy", "magnitude or pip error", "horizon accuracy", "path accuracy", "reversal accuracy"],
        "primary_endpoint": "T+15",
        "secondary_measurement": "Immediate Impulse",
        "denominator_rules": "Use the existing evaluator: exclude no-signal forecasts from directional, magnitude, path, and reversal denominators; strictly score Immediate Impulse only for SUPPORTED Outcomes.",
        "pack_separation": True,
        "single_use": True,
        "retry_boundary": "NO_RETRIES",
        "external_request_ceiling": 0,
        "google_write_ceiling": 0,
        "evaluation_output_destination": "append-only local minimal evaluation evidence",
        "required_attachment_reconciliation": {"run_id": ATTACHMENT_RUN, "attached": 10, "duplicates": 0, "unattached": 0, "population": 32},
        "stop_conditions": ["forecast payload identity or authority gap", "population or denominator conflict", "missing Outcome", "duplicate evaluation row", "unsupported metric", "manifest, authorization, attachment, or lineage mismatch"],
        "evaluation_authorized": True,
    }
    auth["authorization_fingerprint"] = fingerprint(auth)
    return auth


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--controller-commit", required=True)
    args = parser.parse_args()
    auth = build_authorization(args.controller_commit)
    suffix = auth["authorization_fingerprint"].split(":", 1)[1][:20]
    output = BASE / f"PPHB-R1-SLICE-003-SUPPLEMENTARY-EVALUATION-AUTHORIZATION-20260803T081500Z-{suffix}"
    if output.exists():
        raise SystemExit("OUTPUT_ALREADY_EXISTS")
    output.mkdir(parents=True)
    write(output / "authorization.json", auth)
    write(output / "authorization_decision.json", {"decision": "SLICE_003_SUPPLEMENTARY_EVALUATION_AUTHORIZATION_FROZEN", "authorization_id": auth["authorization_id"], "authorization_fingerprint": auth["authorization_fingerprint"], "evaluation_authorized": True, "external_access": 0})
    write(output / "run_manifest.json", {"run_id": output.name, "authorization_id": auth["authorization_id"], "authorization_fingerprint": auth["authorization_fingerprint"], "manifest_id": MANIFEST_ID, "manifest_fingerprint": MANIFEST_FP, "external_requests": 0, "google_writes": 0, "additional_attachment": 0, "evaluation_started": False, "append_only": True})
    print(output)
    print(auth["authorization_id"])
    print(auth["authorization_fingerprint"])


if __name__ == "__main__":
    main()
