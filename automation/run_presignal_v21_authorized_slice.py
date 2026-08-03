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
def end_to_end_authorized_not_started(slice_id: str) -> str:
    return f"{slice_id.replace('-', '_')}_END_TO_END_EXECUTION_AUTHORIZED_NOT_STARTED"
END_TO_END_COMPLETE = "AUTHORIZED_SLICE_COMPLETE"
REQUIRED_AUTH_FIELDS = {
    "authorization_status", "slice_id", "manifest_id", "manifest_sha256",
    "authorized_stage", "authorized_identity_ids", "ceilings", "retry_boundary",
    "contract", "schema_version", "destination",
}
PAIRED_EXCLUSION_MODE = "PAIRED_EXCLUSION_ATTACHMENT"


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


def reject_blocked_authorization(auth_id: str) -> None:
    """Prevent a recorded governance-blocked authorization from being reused."""
    for proof_path in BASE.glob("PPHB-R1-OUTCOME-*-EXECUTION-BLOCKED-*/execution_blocked.json"):
        proof = json.loads(proof_path.read_text())
        if (
            proof.get("authorization_id") == auth_id
            and str(proof.get("decision", "")).endswith("_GOVERNANCE_BLOCKED")
        ):
            fail("AUTHORIZATION_NON_REUSABLE_BLOCKED")


def validate_paired_exclusion_attachment(auth: dict[str, Any], manifest: dict[str, Any], expected_sha: str) -> dict[str, Any]:
    """Validate a no-call attachment authorization against accepted collection evidence."""
    if auth.get("authorization_mode") != PAIRED_EXCLUSION_MODE:
        fail("PAIRED_EXCLUSION_AUTHORIZATION_MODE_CONFLICT")
    if auth.get("authorization_status") != "ACTIVE" or auth.get("single_use") is not True:
        fail("PAIRED_EXCLUSION_AUTHORIZATION_NOT_ACTIVE")
    if auth.get("authorization_fingerprint") != fingerprint(auth):
        fail("AUTHORIZATION_FINGERPRINT_MISMATCH")
    if auth.get("manifest_id") != manifest.get("manifest_id") or auth.get("slice_id") != manifest.get("slice_id"):
        fail("MANIFEST_IDENTITY_CONFLICT")
    if auth.get("manifest_fingerprint") != expected_sha:
        fail("MANIFEST_FINGERPRINT_CONFLICT")
    if auth.get("authorized_stage") != "attachment":
        fail("AUTHORIZED_STAGE_CONFLICT")
    rows = manifest.get("episode_manifest", [])
    excluded = set(auth.get("excluded_episode_ids", []))
    expected_excluded = {"EP_EVENT_4b80366594480b554889", "EP_EVENT_aa41226bcb8107901555"}
    if excluded != expected_excluded:
        fail("PAIRED_EXCLUSION_EPISODE_SCOPE_CONFLICT")
    eligible_rows = [row for row in rows if row.get("episode_id") not in excluded]
    if len(rows) != 12 or len(eligible_rows) != 10:
        fail("PAIRED_EXCLUSION_EPISODE_COUNT_CONFLICT")
    eligible_ids = [row["episode_id"] for row in eligible_rows]
    if auth.get("authorized_identity_ids") != eligible_ids:
        fail("PAIRED_EXCLUSION_IDENTITY_ORDER_CONFLICT")
    population = auth.get("revised_evaluation_population", {})
    if population != {"episodes": 10, "valid_forecasts": 32, "pack_a": 16, "pack_e": 16, "complete_pairs": 16, "unpaired": 0}:
        fail("PAIRED_EXCLUSION_POPULATION_CONFLICT")
    if auth.get("ceilings") != {"max_apps_script_reads": 0, "max_market_data_attempts": 0, "max_total_external_requests": 0, "google_write_ceiling": 0, "max_attachment_records": 10}:
        fail("PAIRED_EXCLUSION_CEILING_CONFLICT")
    if auth.get("retry_boundary") != "NO_AUTOMATIC_RETRIES" or auth.get("evaluation_authorized") is not False:
        fail("PAIRED_EXCLUSION_BOUNDARY_CONFLICT")
    if auth.get("attachment_destination") != "append-only local Outcome attachment evidence":
        fail("ATTACHMENT_DESTINATION_CONFLICT")
    if auth.get("canonical_attachment_entrypoint") != "automation/attach_presignal_v21_outcome_slice_001.py":
        fail("ATTACHMENT_ENTRYPOINT_CONFLICT")
    collection_dir = BASE / auth["collection_run_id"]
    reconciliation = collection_dir / "collection_reconciliation.json"
    candidates = collection_dir / "candidate_outcomes.jsonl"
    if not reconciliation.exists() or not candidates.exists():
        fail("COLLECTION_EVIDENCE_REQUIRED")
    collection = json.loads(reconciliation.read_text())
    if collection.get("candidate_outcomes") != 12 or collection.get("outcome_attachment") != 0 or collection.get("evaluation_calculations") != 0 or collection.get("google_writes") != 0:
        fail("COLLECTION_COMPLETION_FACTS_CONFLICT")
    if set(collection.get("missing_or_terminal_source_episodes", [])) != excluded:
        fail("COLLECTION_EXCLUSION_BINDING_CONFLICT")
    candidate_document = json.loads(candidates.read_text())
    candidate_records = candidate_document if isinstance(candidate_document, list) else [candidate_document]
    valid_candidates = []
    for record in candidate_records:
        candidate = record.get("candidate_outcome", record)
        if candidate.get("status") == "VALID":
            valid_candidates.append({**record, **candidate})
    if {record.get("episode_id") for record in valid_candidates} != set(eligible_ids) or len(valid_candidates) != 10:
        fail("ATTACHMENT_CANDIDATE_POPULATION_CONFLICT")
    if auth.get("eligible_outcome_ids") != [record["outcome_id"] for record in valid_candidates]:
        fail("ATTACHMENT_OUTCOME_IDENTITY_CONFLICT")
    return {"auth": auth, "manifest": manifest, "actual_sha": expected_sha, "manifest_file_sha": expected_sha, "episode_ids": eligible_ids, "valid_candidate_count": len(valid_candidates), "population": population}


def validate(auth_path: Path, manifest_path: Path, expected_sha: str, stage: str, end_to_end: bool = False) -> dict[str, Any]:
    auth = json.loads(auth_path.read_text())
    reject_blocked_authorization(auth.get("authorization_id", ""))
    missing = sorted(REQUIRED_AUTH_FIELDS - set(auth))
    if missing:
        fail("AUTHORIZATION_FIELDS_MISSING:" + ",".join(missing))
    if auth.get("authorization_fingerprint") != fingerprint(auth):
        fail("AUTHORIZATION_FINGERPRINT_MISMATCH")
    manifest = json.loads(manifest_path.read_text())
    rows = manifest.get("episode_manifest", [])
    derived_population = {
        "pack_a": sum(len(row["outcome_collection_identity"]["forecast_references"]["pack_a"]) for row in rows),
        "pack_e": sum(len(row["outcome_collection_identity"]["forecast_references"]["pack_e"]) for row in rows),
        "complete_pack_a_e_pairs": sum(len(row["outcome_collection_identity"]["pack_pairs"]) for row in rows),
    }
    derived_population["valid_forecasts"] = derived_population["pack_a"] + derived_population["pack_e"]
    population = {**derived_population, **manifest.get("authorized_forecast_population", {})}
    actual_sha = file_sha(manifest_path)
    declared_sha = manifest.get("manifest_fingerprint")
    if expected_sha not in {actual_sha, declared_sha} or auth["manifest_sha256"] != expected_sha:
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
        if auth["attachment_write_ceiling"] != {"google_writes": 0, "local_append_only_records": len(rows)}:
            fail("ATTACHMENT_WRITE_CEILING_CONFLICT")
        display_slice = auth["slice_id"].replace("-", " ").title()
        expected_population_prefix = f"{population.get('valid_forecasts')} authoritative valid forecasts mapped one-to-one to {len(rows)} attached {display_slice} Outcomes"
        if not auth["evaluation_population_rule"].startswith(expected_population_prefix) or "terminal-invalid excluded" not in auth["evaluation_population_rule"]:
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
    ids = [row.get("episode_id") for row in rows]
    if len(rows) != 12 or len(set(ids)) != 12 or set(ids) != set(auth["authorized_identity_ids"]):
        fail("AUTHORIZED_IDENTITY_SCOPE_CONFLICT")
    if manifest.get("primary_endpoint") != "T+15" or manifest.get("secondary_measurement") != "Immediate Impulse":
        fail("SCIENTIFIC_BOUNDARY_CONFLICT")
    if sum(len(row["outcome_collection_identity"]["forecast_references"]["pack_a"]) for row in rows) != population.get("pack_a"):
        fail("PACK_A_POPULATION_CONFLICT")
    if sum(len(row["outcome_collection_identity"]["forecast_references"]["pack_e"]) for row in rows) != population.get("pack_e"):
        fail("PACK_E_POPULATION_CONFLICT")
    if sum(len(row["outcome_collection_identity"]["pack_pairs"]) for row in rows) != population.get("complete_pack_a_e_pairs"):
        fail("PAIR_POPULATION_CONFLICT")
    ceilings = auth["ceilings"]
    release_days = {row["release_ts"][:10] for row in rows}
    if end_to_end and "release_days_utc" in auth and sorted(auth["release_days_utc"]) != sorted(release_days):
        fail("RELEASE_DAY_SET_CONFLICT")
    expected = {
        "max_apps_script_reads": len(release_days),
        "max_market_data_attempts": 12,
        "max_total_external_requests": len(release_days) + 12,
        "google_write_ceiling": 0,
    }
    if any(ceilings.get(key) != value for key, value in expected.items()):
        fail("AUTHORIZATION_CEILING_CONFLICT")
    if not end_to_end and set(ceilings) != set(expected):
        fail("AUTHORIZATION_CEILING_CONFLICT")
    if end_to_end and (ceilings.get("max_attachment_records") != len(rows) or ceilings.get("max_evaluation_artifacts") != 1):
        fail("END_TO_END_CEILING_CONFLICT")
    if auth["retry_boundary"] != "NO_AUTOMATIC_RETRIES":
        fail("RETRY_BOUNDARY_CONFLICT")
    return {"auth": auth, "manifest": manifest, "actual_sha": expected_sha, "manifest_file_sha": actual_sha, "episode_ids": ids}


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
        "evaluate": ("PPHB-R1-OUTCOME-EVALUATE", "PPHB-R1-OUTCOME-EVALUATION"),
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
        if auth and auth.get("authorization_mode") == "END_TO_END":
            if (
                run.get("authorization_id") != auth.get("authorization_id")
                or run.get("authorization_fingerprint") != auth.get("authorization_fingerprint")
            ):
                continue
        if stage == "collect":
            reconciliation_path = path / "collection_reconciliation.json"
            decision_path = path / "collection_decision.json"
            candidates_path = path / "candidate_outcomes.jsonl"
            if not reconciliation_path.exists() or not decision_path.exists() or not candidates_path.exists():
                continue
            reconciliation = json.loads(reconciliation_path.read_text())
            decision = json.loads(decision_path.read_text())
            expected_count = len(auth.get("authorized_identity_ids", [])) if auth else reconciliation.get("manifest_episode_count")
            if (
                reconciliation.get("manifest_episode_count") != expected_count
                or reconciliation.get("candidate_outcomes") != expected_count
                or reconciliation.get("schema_validated_candidates") != expected_count
                or reconciliation.get("missing_or_terminal_source_episodes")
                or reconciliation.get("unresolved_identities")
                or reconciliation.get("duplicate_requests") != 0
                or reconciliation.get("google_writes") != 0
                or reconciliation.get("outcome_attachment") != 0
                or reconciliation.get("evaluation_calculations") != 0
                or decision.get("collection_decision") != "OUTCOME_COLLECTION_" + slice_id.replace("-", "_") + "_COMPLETE"
            ):
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
                if (
                    run.get("authorization_id") != auth.get("authorization_id")
                    or run.get("authorization_fingerprint") != auth.get("authorization_fingerprint")
                ):
                    continue
        if stage == "evaluate":
            decision_path = path / "evaluation_decision.json"
            if not decision_path.exists():
                continue
            decision = json.loads(decision_path.read_text())
            expected_episodes = len(auth.get("authorized_identity_ids", [])) if auth else 12
            expected_forecasts = (auth.get("evaluation_population", {}).get("valid_forecasts", 44) if auth else 44)
            if (
                run.get("episode_count") != expected_episodes
                or run.get("forecast_count") != expected_forecasts
                or run.get("google_writes") != 0
                or run.get("external_requests") != 0
                or decision.get("decision") != "OUTCOME_" + slice_id.replace("-", "_") + "_MINIMAL_EVALUATION_COMPLETE"
            ):
                continue
        eligible.append(path)
    if len(eligible) > 1:
        fail("AMBIGUOUS_ACCEPTED_STAGE_ARTIFACT:" + stage)
    return eligible[0] if eligible else None


def execute_end_to_end(auth: dict[str, Any], auth_path: Path, manifest_path: Path, manifest_sha: str, prior: dict[str, Path | None]) -> dict[str, Any]:
    """Delegate each live stage only after the prior stage is accepted."""
    env = __import__("os").environ.copy()
    env.update({
        "PRESIGNAL_OUTCOME_SLICE_ID": auth["slice_id"],
        "PRESIGNAL_OUTCOME_MANIFEST_PATH": str(manifest_path),
        "PRESIGNAL_OUTCOME_EXPECTED_MANIFEST_SHA": manifest_sha,
        "PRESIGNAL_OUTCOME_MAX_GOOGLE_READS": str(auth["ceilings"]["max_apps_script_reads"]),
        "PRESIGNAL_OUTCOME_MAX_PROVIDER_ATTEMPTS": str(auth["ceilings"]["max_market_data_attempts"]),
        "PRESIGNAL_OUTCOME_MAX_TOTAL_EXTERNAL": str(auth["ceilings"]["max_total_external_requests"]),
        "PRESIGNAL_OUTCOME_AUTHORIZATION_ID": auth["authorization_id"],
        "PRESIGNAL_OUTCOME_AUTHORIZATION_FINGERPRINT": auth["authorization_fingerprint"],
        "PRESIGNAL_EVALUATION_AUTH_PATH": str(auth_path),
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
    completed_decision = "AUTHORIZED_" + auth["slice_id"].replace("-", "_") + "_END_TO_END_COMPLETE"
    return {"decision": completed_decision, "progression": ["COLLECTION_COMPLETE", "ATTACHMENT_RECONCILED", "MINIMAL_EVALUATION_COMPLETE", completed_decision]}


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
    # Stage entrypoints persist repository-relative evidence paths; resolve
    # caller-supplied paths before delegation so resume is location-stable.
    args.authorization = args.authorization.resolve()
    args.manifest = args.manifest.resolve()
    checked = validate(args.authorization, args.manifest, args.expected_manifest_sha, args.stage, end_to_end=args.end_to_end)
    auth = checked["auth"]
    manifest = checked["manifest"]
    prior = {stage: accepted_stage_artifact(stage, auth["slice_id"], args.expected_manifest_sha, auth) for stage in ("collect", "attach", "evaluate")}
    if args.end_to_end:
        route_proof = simulate_end_to_end_route() if args.mock_clean_route else None
        if auth["authorization_status"] != "ACTIVE":
            decision = END_TO_END_STOP
        elif args.offline_validation:
            decision = auth.get("live_stop_state_before_execution", end_to_end_authorized_not_started(auth["slice_id"]))
        else:
            if route_proof is not None and route_proof["decision"] != END_TO_END_COMPLETE:
                fail("END_TO_END_ROUTE_BLOCKED")
            route_proof = execute_end_to_end(auth, args.authorization, args.manifest, args.expected_manifest_sha, prior)
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
        "manifest_file_sha256": checked["manifest_file_sha"],
        "authorized_stage": auth["authorized_stage"],
        "recognized_episode_count": len(checked["episode_ids"]),
        "recognized_valid_forecast_count": manifest.get("authorized_forecast_population", {}).get("valid_forecasts"),
        "recognized_pack_a_count": manifest.get("authorized_forecast_population", {}).get("pack_a"),
        "recognized_pack_e_count": manifest.get("authorized_forecast_population", {}).get("pack_e"),
        "recognized_complete_pairs": manifest.get("authorized_forecast_population", {}).get("complete_pack_a_e_pairs"),
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
