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
END_TO_END_STOP = "MANIFEST_ACCEPTED_END_TO_END_AUTHORIZATION_REQUIRED"
END_TO_END_AUTHORIZED_NOT_STARTED = "SLICE_002_END_TO_END_EXECUTION_AUTHORIZED_NOT_STARTED"
END_TO_END_COMPLETE = "AUTHORIZED_SLICE_COMPLETE"
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


def validate(auth_path: Path, manifest_path: Path, expected_sha: str, stage: str, end_to_end: bool = False) -> dict[str, Any]:
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
    if end_to_end:
        required = {"authorization_id", "authorization_schema_version", "controller_version", "controller_commit", "authorization_mode", "outcome_collection_identity_ids", "authorized_attachment_identity_ids", "attachment_destination", "attachment_write_ceiling", "evaluation_population_rule", "evaluation_output_destination", "permitted_metrics", "stage_sequence", "stage_stop_conditions", "resume_authority", "single_use"}
        missing_end_to_end = sorted(required - set(auth))
        if missing_end_to_end:
            fail("END_TO_END_AUTHORITY_FIELDS_MISSING:" + ",".join(missing_end_to_end))
        if auth["authorization_mode"] != "END_TO_END" or auth["authorized_stage"] != "end_to_end":
            fail("END_TO_END_AUTHORIZATION_MODE_CONFLICT")
        if set(auth["outcome_collection_identity_ids"]) != {
            row["outcome_collection_identity"]["duplicate_prevention_identity"] for row in manifest.get("episode_manifest", [])
        }:
            fail("OUTCOME_COLLECTION_IDENTITY_CONFLICT")
        if auth["attachment_destination"] != "append-only local Outcome attachment evidence":
            fail("ATTACHMENT_DESTINATION_CONFLICT")
        if set(auth["authorized_attachment_identity_ids"]) != set(auth["outcome_collection_identity_ids"]):
            fail("ATTACHMENT_IDENTITY_SCOPE_CONFLICT")
        if auth["attachment_write_ceiling"] != {"google_writes": 0, "local_append_only_records": 12}:
            fail("ATTACHMENT_WRITE_CEILING_CONFLICT")
        if not auth["evaluation_population_rule"].startswith("44 authoritative valid forecasts mapped one-to-one to 12 attached Slice 002 Outcomes") or "terminal-invalid excluded" not in auth["evaluation_population_rule"]:
            fail("EVALUATION_POPULATION_RULE_CONFLICT")
        permitted_metrics = {
            "T+15 directional accuracy",
            "Immediate Impulse directional accuracy",
            "magnitude or pip error",
            "horizon accuracy",
            "path accuracy",
            "reversal accuracy",
        }
        if set(auth["permitted_metrics"]) != permitted_metrics:
            fail("PERMITTED_METRICS_CONFLICT")
        if auth["stage_sequence"] != ["call_free_preflight", "collection", "collection_reconciliation", "attachment", "attachment_reconciliation", "minimal_evaluation", "final_slice_reconciliation"]:
            fail("STAGE_SEQUENCE_CONFLICT")
        if auth["single_use"] is not True:
            fail("SINGLE_USE_CONFLICT")
    elif stage != auth["authorized_stage"] and not (stage == "manifest" and auth["authorized_stage"] == "collect"):
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
    expected = {"max_apps_script_reads": 3, "max_market_data_attempts": 12, "max_total_external_requests": 15, "google_write_ceiling": 0}
    if any(ceilings.get(key) != value for key, value in expected.items()):
        fail("AUTHORIZATION_CEILING_CONFLICT")
    if not end_to_end and set(ceilings) != set(expected):
        fail("AUTHORIZATION_CEILING_CONFLICT")
    if end_to_end and (ceilings.get("max_attachment_records") != 12 or ceilings.get("max_evaluation_artifacts") != 1):
        fail("END_TO_END_CEILING_CONFLICT")
    if auth["retry_boundary"] != "NO_AUTOMATIC_RETRIES":
        fail("RETRY_BOUNDARY_CONFLICT")
    return {"auth": auth, "manifest": manifest, "actual_sha": actual_sha, "episode_ids": ids}


def simulate_end_to_end_route(stage_statuses: dict[str, str] | None = None) -> dict[str, Any]:
    """Resolve mocked stage outcomes without invoking any stage implementation."""
    statuses = stage_statuses or {"collection": "COMPLETE", "attachment": "RECONCILED", "evaluation": "COMPLETE", "final": "COMPLETE"}
    expected = (("collection", "COMPLETE", "COLLECTION_COMPLETE_ATTACHMENT_AUTHORIZATION_REQUIRED"), ("attachment", "RECONCILED", "ATTACHMENT_RECONCILED_EVALUATION_AUTHORIZATION_REQUIRED"), ("evaluation", "COMPLETE", "MINIMAL_EVALUATION_COMPLETE"), ("final", "COMPLETE", END_TO_END_COMPLETE))
    for stage, accepted, stop in expected:
        state = statuses.get(stage)
        if state != accepted:
            return {"decision": "END_TO_END_ROUTE_STOPPED", "failed_stage": stage, "state": state or "MISSING", "requires_new_authorization": True}
    return {"decision": END_TO_END_COMPLETE, "progression": ["COLLECTION_COMPLETE", "ATTACHMENT_RECONCILED", "MINIMAL_EVALUATION_COMPLETE", END_TO_END_COMPLETE], "requires_new_authorization": False}


def accepted_stage_artifact(stage: str, slice_id: str, manifest_sha: str, auth: dict[str, Any] | None = None) -> Path | None:
    prefixes = {
        "collect": ("PPHB-R1-OUTCOME-COLLECTION",),
        "attach": ("PPHB-R1-OUTCOME-ATTACH", "PPHB-R1-OUTCOME-ATTACHMENT"),
        "evaluate": ("PPHB-R1-OUTCOME-EVALUATION",),
    }
    candidates: list[Path] = []
    for prefix in prefixes.get(stage, ()):
        candidates.extend(BASE.glob(f"{prefix}-{slice_id}-*"))
    eligible: list[Path] = []
    for path in sorted(set(candidates)):
        run_path = path / "run_manifest.json"
        if not run_path.exists():
            continue
        run = json.loads(run_path.read_text())
        if run.get("run_id") != path.name or run.get("manifest_sha256") != manifest_sha:
            continue
        if stage == "attach":
            reconciliation_path = path / "attachment_reconciliation.json"
            decision_path = path / "attachment_decision.json"
            if not reconciliation_path.exists() or not decision_path.exists():
                continue
            reconciliation = json.loads(reconciliation_path.read_text())
            decision = json.loads(decision_path.read_text())
            if (
                run.get("candidate_count") != 12
                or run.get("attachment_count") != 12
                or run.get("google_writes") != 0
                or reconciliation.get("attached_outcome_count") != 12
                or reconciliation.get("unattached_candidate_count") != 0
                or reconciliation.get("duplicate_or_conflicting_attachments") != 0
                or reconciliation.get("unresolved_identities")
                or decision.get("decision") != "OUTCOME_" + slice_id.replace("-", "_") + "_ATTACHED_AND_RECONCILED"
            ):
                continue
            if auth and auth.get("authorization_mode") == "END_TO_END":
                proof_paths = list(BASE.glob("PPHB-R1-OUTCOME-SLICE-002-END-TO-END-AUTHORIZATION-*/attachment_execution_stop.json"))
                proofs = []
                for proof_path in proof_paths:
                    proof = json.loads(proof_path.read_text())
                    if (
                        proof.get("authorization_id") == auth.get("authorization_id")
                        and proof.get("authorization_fingerprint") == auth.get("authorization_fingerprint")
                        and proof.get("attachment_run_id") == path.name
                        and proof.get("attachment_result", {}).get("attached_records") == 12
                        and proof.get("attachment_result", {}).get("duplicates") == 0
                        and proof.get("attachment_result", {}).get("unattached_records") == 0
                    ):
                        proofs.append(proof_path)
                if len(proofs) != 1:
                    continue
        eligible.append(path)
    if len(eligible) > 1:
        fail("AMBIGUOUS_ACCEPTED_STAGE_ARTIFACT:" + stage)
    return eligible[0] if eligible else None


def execute_end_to_end(auth: dict[str, Any], manifest_path: Path, manifest_sha: str, prior: dict[str, Path | None]) -> dict[str, Any]:
    """Delegate each live stage only after the prior stage is accepted."""
    env = __import__("os").environ.copy()
    env.update({
        "PRESIGNAL_OUTCOME_SLICE_ID": auth["slice_id"],
        "PRESIGNAL_OUTCOME_MANIFEST_PATH": str(manifest_path),
        "PRESIGNAL_OUTCOME_EXPECTED_MANIFEST_SHA": manifest_sha,
        "PRESIGNAL_OUTCOME_MAX_GOOGLE_READS": str(auth["ceilings"]["max_apps_script_reads"]),
        "PRESIGNAL_OUTCOME_MAX_PROVIDER_ATTEMPTS": str(auth["ceilings"]["max_market_data_attempts"]),
        "PRESIGNAL_OUTCOME_MAX_TOTAL_EXTERNAL": str(auth["ceilings"]["max_total_external_requests"]),
    })
    scripts = {
        "collect": "collect_presignal_v21_outcome_slice_001.py",
        "attach": "attach_presignal_v21_outcome_slice_001.py",
        "evaluate": "evaluate_presignal_v21_outcome_slice_001.py",
    }
    for stage in ("collect", "attach", "evaluate"):
        if prior[stage] is not None:
            continue
        if stage == "attach":
            collection = accepted_stage_artifact("collect", auth["slice_id"], manifest_sha, auth)
            if collection is None:
                fail("COLLECTION_COMPLETION_REQUIRED")
            env["PRESIGNAL_OUTCOME_COLLECTION_RUN"] = collection.name
        if stage == "evaluate":
            attachment = accepted_stage_artifact("attach", auth["slice_id"], manifest_sha, auth)
            if attachment is None:
                fail("ATTACHMENT_COMPLETION_REQUIRED")
            env["PRESIGNAL_OUTCOME_ATTACHMENT_RUN"] = attachment.name
        run_id = "PPHB-R1-OUTCOME-" + stage.upper() + "-" + auth["slice_id"] + "-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + manifest_sha[-12:]
        command = [sys.executable, str(ROOT / "automation" / scripts[stage])]
        if stage in {"attach", "evaluate"}:
            command.extend(["--run-id", run_id])
        result = subprocess.run(command, cwd=ROOT, env=env, check=False)
        if result.returncode:
            fail("END_TO_END_STAGE_BLOCKED:" + stage)
        if accepted_stage_artifact(stage, auth["slice_id"], manifest_sha, auth) is None:
            fail("END_TO_END_STAGE_COMPLETION_UNPROVEN:" + stage)
    return {"decision": END_TO_END_COMPLETE, "progression": ["COLLECTION_COMPLETE", "ATTACHMENT_RECONCILED", "MINIMAL_EVALUATION_COMPLETE", END_TO_END_COMPLETE]}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--authorization", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--expected-manifest-sha", required=True)
    parser.add_argument("--stage", choices=tuple(STOP_STATES), default="manifest")
    parser.add_argument("--end-to-end", action="store_true")
    parser.add_argument("--mock-clean-route", action="store_true", help="Prove end-to-end transitions with local mocked stage results.")
    parser.add_argument("--offline-validation", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    checked = validate(args.authorization, args.manifest, args.expected_manifest_sha, args.stage, end_to_end=args.end_to_end)
    auth = checked["auth"]
    manifest = checked["manifest"]
    prior = {stage: accepted_stage_artifact(stage, auth["slice_id"], args.expected_manifest_sha, auth) for stage in ("collect", "attach", "evaluate")}
    if args.end_to_end:
        route_proof = simulate_end_to_end_route() if args.mock_clean_route else None
        if auth["authorization_status"] != "ACTIVE":
            decision = END_TO_END_STOP
        elif args.offline_validation:
            decision = END_TO_END_AUTHORIZED_NOT_STARTED
        else:
            if route_proof is not None and route_proof["decision"] != END_TO_END_COMPLETE:
                fail("END_TO_END_ROUTE_BLOCKED")
            route_proof = execute_end_to_end(auth, args.manifest, args.expected_manifest_sha, prior)
            decision = route_proof["decision"]
    elif args.stage == "manifest":
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
        "end_to_end_mode": args.end_to_end,
        "mock_clean_route": simulate_end_to_end_route() if args.end_to_end and args.mock_clean_route else None,
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
