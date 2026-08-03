#!/usr/bin/env python3
"""Bounded controller for one explicitly authorized Outcome slice."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "outputs" / "presignal_v21_full_round_1_forecast_execution"
CONTROL = BASE / ".authorized_slice_controller"
STOP_STATES = {
    "manifest": "MANIFEST_ACCEPTED_COLLECTION_AUTHORIZATION_REQUIRED",
    "collect": "COLLECTION_COMPLETE_ATTACHMENT_AUTHORIZATION_REQUIRED",
    "attach": "ATTACHMENT_RECONCILED_EVALUATION_AUTHORIZATION_REQUIRED",
    "evaluate": "MINIMAL_EVALUATION_COMPLETE",
}
REQUIRED_AUTH_FIELDS = {
    "authorization_status", "slice_id", "manifest_id", "manifest_sha256",
    "authorized_stage", "authorized_identity_ids", "ceilings", "retry_boundary",
    "contract", "schema_version", "destination",
}


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def fingerprint(value: dict[str, Any]) -> str:
    body = {key: value[key] for key in value if key != "authorization_fingerprint"}
    return "sha256:" + hashlib.sha256(canonical(body).encode()).hexdigest()


def file_sha(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def fail(message: str) -> None:
    raise SystemExit(message)


def validate(auth_path: Path, manifest_path: Path, expected_sha: str, stage: str) -> dict[str, Any]:
    auth = json.loads(auth_path.read_text())
    missing = sorted(REQUIRED_AUTH_FIELDS - set(auth))
    if missing:
        fail("AUTHORIZATION_FIELDS_MISSING:" + ",".join(missing))
    if auth.get("authorization_fingerprint") != fingerprint(auth):
        fail("AUTHORIZATION_FINGERPRINT_MISMATCH")
    manifest = json.loads(manifest_path.read_text())
    actual_sha = file_sha(manifest_path)
    if actual_sha != expected_sha or auth["manifest_sha256"] != expected_sha:
        fail("MANIFEST_FINGERPRINT_CONFLICT")
    if auth["manifest_id"] != manifest.get("manifest_id") or auth["slice_id"] != manifest.get("slice_id"):
        fail("MANIFEST_IDENTITY_CONFLICT")
    if stage != auth["authorized_stage"] and not (stage == "manifest" and auth["authorized_stage"] == "collect"):
        fail("AUTHORIZED_STAGE_CONFLICT")
    if auth["contract"] != manifest.get("forecast_contract") or auth["schema_version"] != manifest.get("outcome_schema_version"):
        fail("CONTRACT_SCHEMA_CONFLICT")
    if auth["destination"] != manifest.get("collection_destination"):
        fail("DESTINATION_CONFLICT")
    rows = manifest.get("episode_manifest", [])
    ids = [row.get("episode_id") for row in rows]
    if len(rows) != 12 or len(set(ids)) != 12 or set(ids) != set(auth["authorized_identity_ids"]):
        fail("AUTHORIZED_IDENTITY_SCOPE_CONFLICT")
    if manifest.get("primary_endpoint") != "T+15" or manifest.get("secondary_measurement") != "Immediate Impulse":
        fail("SCIENTIFIC_BOUNDARY_CONFLICT")
    if sum(len(row["outcome_collection_identity"]["forecast_references"]["pack_a"]) for row in rows) != 22:
        fail("PACK_A_POPULATION_CONFLICT")
    if sum(len(row["outcome_collection_identity"]["forecast_references"]["pack_e"]) for row in rows) != 22:
        fail("PACK_E_POPULATION_CONFLICT")
    if sum(len(row["outcome_collection_identity"]["pack_pairs"]) for row in rows) != 22:
        fail("PAIR_POPULATION_CONFLICT")
    ceilings = auth["ceilings"]
    expected = {
        "max_apps_script_reads": 3,
        "max_market_data_attempts": 12,
        "max_total_external_requests": 15,
        "google_write_ceiling": 0,
    }
    if ceilings != expected:
        fail("AUTHORIZATION_CEILING_CONFLICT")
    if auth["retry_boundary"] != "NO_AUTOMATIC_RETRIES":
        fail("RETRY_BOUNDARY_CONFLICT")
    return {"auth": auth, "manifest": manifest, "actual_sha": actual_sha, "episode_ids": ids}


def accepted_stage_artifact(stage: str, slice_id: str, manifest_sha: str) -> Path | None:
    prefixes = {"collect": "PPHB-R1-OUTCOME-COLLECTION", "attach": "PPHB-R1-OUTCOME-ATTACHMENT", "evaluate": "PPHB-R1-OUTCOME-EVALUATION"}
    prefix = prefixes.get(stage)
    if not prefix:
        return None
    for path in BASE.glob(f"{prefix}-{slice_id}-*"):
        run = path / "run_manifest.json"
        if run.exists():
            value = json.loads(run.read_text())
            if value.get("manifest_sha256") == manifest_sha:
                return path
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--authorization", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--expected-manifest-sha", required=True)
    parser.add_argument("--stage", choices=tuple(STOP_STATES), default="manifest")
    parser.add_argument("--offline-validation", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    checked = validate(args.authorization, args.manifest, args.expected_manifest_sha, args.stage)
    auth = checked["auth"]
    manifest = checked["manifest"]
    prior = {stage: accepted_stage_artifact(stage, auth["slice_id"], args.expected_manifest_sha) for stage in ("collect", "attach", "evaluate")}
    if args.stage == "manifest":
        decision = STOP_STATES["manifest"]
    elif prior[args.stage] is not None:
        decision = STOP_STATES[args.stage]
    elif auth["authorization_status"] != "ACTIVE":
        fail("STAGE_AUTHORIZATION_NOT_ACTIVE")
    elif args.offline_validation:
        fail("OFFLINE_STAGE_EXECUTION_NOT_PERMITTED")
    else:
        scripts = {"collect": "collect_presignal_v21_outcome_slice_001.py", "attach": "attach_presignal_v21_outcome_slice_001.py", "evaluate": "evaluate_presignal_v21_outcome_slice_001.py"}
        command = [sys.executable, str(ROOT / "automation" / scripts[args.stage])]
        result = subprocess.run(command, cwd=ROOT, check=False)
        if result.returncode:
            fail("STAGE_EXECUTION_BLOCKED")
        decision = STOP_STATES[args.stage]
    evidence = {
        "controller_version": "AUTHORIZED_SLICE_CONTROLLER_V1",
        "decision": decision,
        "slice_id": auth["slice_id"],
        "manifest_id": manifest["manifest_id"],
        "manifest_sha256": checked["actual_sha"],
        "authorized_stage": auth["authorized_stage"],
        "recognized_episode_count": len(checked["episode_ids"]),
        "recognized_valid_forecast_count": 44,
        "recognized_pack_a_count": 22,
        "recognized_pack_e_count": 22,
        "recognized_complete_pairs": 22,
        "recognized_ceilings": auth["ceilings"],
        "external_access": {"google_reads": 0, "market_data_attempts": 0, "total_external_requests": 0, "google_writes": 0},
        "prior_stage_artifacts": {key: str(value) if value else None for key, value in prior.items()},
        "automatic_stage_transition": False,
        "append_only": True,
        "generated_ts": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
    }
    if args.output:
        write(args.output, evidence)
    else:
        print(json.dumps(evidence, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
