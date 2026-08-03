#!/usr/bin/env python3
"""Freeze the no-call Slice 003 paired-exclusion attachment authorization."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "outputs" / "presignal_v21_full_round_1_forecast_execution"
MANIFEST_DIR = BASE / "PPHB-R1-OUTCOME-COLLECTION-MANIFEST-SLICE-003-20260803T154000Z-c15ec51effbb6ac5d26a"
COLLECTION_RUN_ID = "PPHB-R1-OUTCOME-COLLECTION-SLICE-003-20260803T071136Z-fc2fd1815bd5"
REVIEW_ID = "PPHB-R1-SLICE-003-UNAVAILABLE-OUTCOME-GOVERNANCE-REVIEW-20260803T073000Z"
AUTHORIZATION_ID = "PPHB-R1-SLICE-003-PAIRED-EXCLUSION-ATTACHMENT-AUTHORIZATION-20260803T080000Z"
MANIFEST_FP = "sha256:c15ec51effbb6ac5d26a48ead4c28504d0f5fc8e8a157e650726fc2fd1815bd5"
EXCLUDED = {"EP_EVENT_4b80366594480b554889", "EP_EVENT_aa41226bcb8107901555"}


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def fingerprint(value: dict[str, Any]) -> str:
    body = {key: value[key] for key in value if key != "authorization_fingerprint"}
    return "sha256:" + hashlib.sha256(canonical(body).encode()).hexdigest()


def write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def build_authorization(controller_commit: str) -> tuple[dict[str, Any], dict[str, Any]]:
    manifest = json.loads((MANIFEST_DIR / "slice_003_manifest.json").read_text())
    rows = manifest["episode_manifest"]
    eligible_rows = [row for row in rows if row["episode_id"] not in EXCLUDED]
    candidate_path = BASE / COLLECTION_RUN_ID / "candidate_outcomes.jsonl"
    candidate_document = json.loads(candidate_path.read_text())
    candidate_records = candidate_document if isinstance(candidate_document, list) else [candidate_document]
    valid_candidates = []
    for record in candidate_records:
        candidate = record.get("candidate_outcome", record)
        if candidate.get("status") == "VALID":
            valid_candidates.append({**record, **candidate})
    if len(rows) != 12 or len(eligible_rows) != 10 or len(valid_candidates) != 10:
        raise SystemExit("REVISED_POPULATION_NOT_PROVABLE")
    if {record["episode_id"] for record in valid_candidates} != {row["episode_id"] for row in eligible_rows}:
        raise SystemExit("OUTCOME_IDENTITY_SCOPE_CONFLICT")
    excluded_forecasts = [
        call_id
        for row in rows if row["episode_id"] in EXCLUDED
        for pack in ("pack_a", "pack_e")
        for call_id in row["outcome_collection_identity"]["forecast_references"][pack]
    ]
    population = {"episodes": 10, "valid_forecasts": 32, "pack_a": 16, "pack_e": 16, "complete_pairs": 16, "unpaired": 0}
    auth = {
        "authorization_id": AUTHORIZATION_ID,
        "authorization_schema_version": "AUTHORIZED_SLICE_PAIRED_EXCLUSION_ATTACHMENT_V1",
        "authorization_status": "ACTIVE",
        "authorization_mode": "PAIRED_EXCLUSION_ATTACHMENT",
        "authorized_stage": "attachment",
        "slice_id": manifest["slice_id"],
        "manifest_id": manifest["manifest_id"],
        "manifest_fingerprint": MANIFEST_FP,
        "controller_version": "AUTHORIZED_SLICE_CONTROLLER_V1_PAIRED_EXCLUSION_ATTACHMENT",
        "controller_commit": controller_commit,
        "contract_binding": "PPHB-R1-PROSPECTIVE-SLICE-EXECUTION-CONTRACT-20260803T060000Z",
        "collection_run_id": COLLECTION_RUN_ID,
        "governance_review_id": REVIEW_ID,
        "authorized_identity_ids": [row["episode_id"] for row in eligible_rows],
        "eligible_outcome_ids": [record["outcome_id"] for record in valid_candidates],
        "excluded_episode_ids": sorted(EXCLUDED),
        "excluded_forecast_call_ids": excluded_forecasts,
        "exclusion_rule": "Exclude both PACK_A and PACK_E forecast references for every excluded Episode; retain no single-Pack forecast.",
        "revised_evaluation_population": population,
        "ceilings": {"max_apps_script_reads": 0, "max_market_data_attempts": 0, "max_total_external_requests": 0, "google_write_ceiling": 0, "max_attachment_records": 10},
        "retry_boundary": "NO_AUTOMATIC_RETRIES",
        "contract": manifest["forecast_contract"],
        "schema_version": manifest["outcome_schema_version"],
        "attachment_destination": "append-only local Outcome attachment evidence",
        "canonical_attachment_entrypoint": "automation/attach_presignal_v21_outcome_slice_001.py",
        "required_collection_artifact": {"run_id": COLLECTION_RUN_ID, "required_files": ["collection_reconciliation.json", "candidate_outcomes.jsonl"], "manifest_fingerprint": MANIFEST_FP},
        "attachment_reconciliation_requirements": {"attached": 10, "duplicates": 0, "unattached_eligible": 0, "excluded_episode_attachments": 0, "unresolved_identities": 0, "google_writes": 0},
        "evaluation_authorized": False,
        "post_attachment_stop_state": "SLICE_003_ATTACHMENT_RECONCILED_EVALUATION_AUTHORIZATION_REQUIRED",
        "stage_sequence": ["paired_exclusion_application", "attachment", "attachment_reconciliation"],
        "stop_before": "evaluation",
        "single_use": True,
        "resume_authority": "Resume only from accepted append-only collection evidence or accepted attachment reconciliation; never recollect or repeat an accepted attachment.",
        "duplicate_prevention": "Bind each attachment to manifest, collection run, governance review, authorization, Episode, candidate Outcome ID and candidate fingerprint; fail closed on duplicate or outside-scope identity.",
        "exclusion_evidence": {"governance_decision": "AUTHORIZE_PAIRED_EXCLUSION_OF_TWO_UNAVAILABLE_EPISODES", "preserve_unavailable_candidates": True, "preserve_blocked_authorizations": True},
    }
    auth["authorization_fingerprint"] = fingerprint(auth)
    proof = {"original_episodes": 12, "excluded_episodes": 2, "eligible_episodes": 10, "valid_candidates": 10, "eligible_forecasts": 32, "pack_a": 16, "pack_e": 16, "complete_pairs": 16, "unpaired": 0, "excluded_episode_ids": sorted(EXCLUDED), "excluded_forecast_call_ids": excluded_forecasts, "eligible_outcome_ids": auth["eligible_outcome_ids"], "external_access": {"apps_script_reads": 0, "market_data_attempts": 0, "total_external_requests": 0, "google_writes": 0, "retries": 0, "attachment": 0, "evaluation": 0}}
    return auth, proof


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--controller-commit", required=True)
    args = parser.parse_args()
    auth, proof = build_authorization(args.controller_commit)
    suffix = auth["authorization_fingerprint"].split(":", 1)[1][:20]
    output = BASE / f"PPHB-R1-SLICE-003-PAIRED-EXCLUSION-ATTACHMENT-AUTHORIZATION-20260803T080000Z-{suffix}"
    if output.exists():
        raise SystemExit("OUTPUT_ALREADY_EXISTS")
    output.mkdir(parents=True)
    write(output / "authorization.json", auth)
    write(output / "paired_exclusion_proof.json", {**proof, "manifest_id": auth["manifest_id"], "manifest_fingerprint": MANIFEST_FP, "governance_review_id": REVIEW_ID})
    write(output / "controller_acceptance_requirements.json", {"decision": "SLICE_003_PAIRED_EXCLUSION_ATTACHMENT_AUTHORIZATION_FROZEN", "readiness": "SLICE_003_ATTACHMENT_EXECUTION_READY", "live_state": "SLICE_003_PAIRED_EXCLUSION_ATTACHMENT_AUTHORIZED_NOT_STARTED", "evaluation_authorized": False, "external_access": 0})
    write(output / "run_manifest.json", {"run_id": output.name, "authorization_id": auth["authorization_id"], "authorization_fingerprint": auth["authorization_fingerprint"], "manifest_id": auth["manifest_id"], "manifest_fingerprint": MANIFEST_FP, "provider_calls": 0, "google_reads": 0, "market_data_calls": 0, "google_writes": 0, "attachment_records": 0, "evaluation": 0, "append_only": True})
    print(output)
    print(auth["authorization_id"])
    print(auth["authorization_fingerprint"])


if __name__ == "__main__":
    main()
