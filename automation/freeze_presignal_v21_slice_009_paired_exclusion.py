#!/usr/bin/env python3
"""Freeze a no-call paired-exclusion continuation for Slice 009."""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "outputs/presignal_v21_full_round_1_forecast_execution"
MANIFEST_DIR = BASE / "PPHB-R1-OUTCOME-COLLECTION-MANIFEST-SLICE-009-20260803T180000Z-1f8ae1ba9312ee2dd121"
COLLECTION_RUN = "PPHB-R1-OUTCOME-COLLECTION-SLICE-009-20260803T102627Z-af38aa3c6a26"
MANIFEST_FP = "sha256:1f8ae1ba9312ee2dd121b7d3fa68c4b20360720b71fce9364222af38aa3c6a26"
EXCLUDED = {"EP_EVENT_2efc8caf43d7a31210c9", "EP_EVENT_3cf33832dc4ce9030be9", "EP_EVENT_ccb253c98e5dace78f0e", "EP_EVENT_f1cc87e112927700eb4b"}
AUTH_ID = "PPHB-R1-SLICE-009-PAIRED-EXCLUSION-CONTINUATION-AUTHORIZATION-20260803T103000Z"


def canon(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def fp(value):
    body = {key: value[key] for key in value if key != "authorization_fingerprint"}
    return "sha256:" + hashlib.sha256(canon(body).encode()).hexdigest()


def main():
    manifest = json.loads((MANIFEST_DIR / "slice_009_manifest.json").read_text())
    rows = manifest["episode_manifest"]
    candidates = json.loads((BASE / COLLECTION_RUN / "candidate_outcomes.jsonl").read_text())
    unavailable = {row["episode_id"] for row in candidates if row.get("status") == "UNAVAILABLE"}
    if unavailable != EXCLUDED:
        raise SystemExit("UNAVAILABLE_SCOPE_CONFLICT")
    eligible = [row for row in rows if row["episode_id"] not in EXCLUDED]
    valid = [row for row in candidates if row.get("status") == "VALID"]
    if len(rows) != 12 or len(eligible) != 8 or {row["episode_id"] for row in valid} != {row["episode_id"] for row in eligible}:
        raise SystemExit("PAIRED_POPULATION_NOT_PROVABLE")
    excluded_calls = [call for row in rows if row["episode_id"] in EXCLUDED for pack in ("pack_a", "pack_e") for call in row["outcome_collection_identity"]["forecast_references"][pack]]
    population = {"episodes": 8, "valid_forecasts": 28, "pack_a": 14, "pack_e": 14, "complete_pairs": 14, "unpaired": 0}
    auth = {"authorization_id": AUTH_ID, "authorization_schema_version": "AUTHORIZED_SLICE_PAIRED_EXCLUSION_END_TO_END_V1", "authorization_status": "ACTIVE", "authorization_mode": "PAIRED_EXCLUSION_END_TO_END", "authorized_stage": "attachment", "slice_id": "SLICE-009", "manifest_id": manifest["manifest_id"], "manifest_fingerprint": MANIFEST_FP, "controller_version": "AUTHORIZED_SLICE_CONTROLLER_V1_PAIRED_EXCLUSION_END_TO_END", "controller_commit": "9562076ea720f4b56073e308d6c6535e77569eda", "contract_binding": "PPHB-R1-PROSPECTIVE-SLICE-EXECUTION-CONTRACT-20260803T060000Z", "collection_run_id": COLLECTION_RUN, "authorized_identity_ids": [row["episode_id"] for row in eligible], "eligible_outcome_ids": [row["outcome_id"] for row in valid], "excluded_episode_ids": sorted(EXCLUDED), "excluded_forecast_call_ids": excluded_calls, "exclusion_rule": "Exclude both Pack A and Pack E forecast references for every unavailable Episode; retain no single-Pack forecast.", "revised_evaluation_population": population, "ceilings": {"max_apps_script_reads": 0, "max_market_data_attempts": 0, "max_total_external_requests": 0, "google_write_ceiling": 0, "max_attachment_records": 8}, "retry_boundary": "NO_AUTOMATIC_RETRIES", "contract": manifest["forecast_contract"], "schema_version": manifest["outcome_schema_version"], "attachment_destination": "append-only local Outcome attachment evidence", "canonical_attachment_entrypoint": "automation/attach_presignal_v21_outcome_slice_001.py", "attachment_authorized": True, "evaluation_authorized": True, "evaluation_population": population, "permitted_metrics": ["T+15 directional accuracy", "Immediate Impulse directional accuracy", "magnitude or pip error", "horizon accuracy", "path accuracy", "reversal accuracy"], "primary_endpoint": "T+15", "secondary_measurement": "Immediate Impulse", "single_use": True, "resume_authority": "Resume only from accepted append-only collection evidence; never recollect or repeat accepted attachment.", "paired_exclusion_governance": "Existing accepted symmetric paired-exclusion rule; unavailable values remain preserved and unattached.", "new_external_requests": 0, "google_writes": 0, "retries": 0}
    auth["authorization_fingerprint"] = fp(auth)
    suffix = auth["authorization_fingerprint"].split(":", 1)[1][:20]
    out = BASE / f"PPHB-R1-SLICE-009-PAIRED-EXCLUSION-CONTINUATION-AUTHORIZATION-20260803T103000Z-{suffix}"
    out.mkdir(parents=True)
    proof = {"decision": "AUTHORIZE_PAIRED_EXCLUSION_OF_FOUR_UNAVAILABLE_EPISODES", "excluded_episode_ids": sorted(EXCLUDED), "excluded_forecast_call_ids": excluded_calls, "eligible_episode_ids": auth["authorized_identity_ids"], "population": population, "collection_run_id": COLLECTION_RUN, "manifest_fingerprint": MANIFEST_FP, "new_external_requests": 0, "google_writes": 0, "retries": 0, "preserved_unavailable_evidence": True}
    for name, value in (("authorization.json", auth), ("paired_exclusion_proof.json", proof), ("run_manifest.json", {"run_id": out.name, "authorization_id": AUTH_ID, "authorization_fingerprint": auth["authorization_fingerprint"], "manifest_fingerprint": MANIFEST_FP, "external_requests": 0, "writes": 0, "retries": 0, "append_only": True})):
        (out / name).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    print(out / "authorization.json")
    print(auth["authorization_fingerprint"])


if __name__ == "__main__":
    main()
