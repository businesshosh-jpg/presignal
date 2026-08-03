#!/usr/bin/env python3
"""Bounded authorization and stage runner for one immutable Outcome slice."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "outputs" / "presignal_v21_full_round_1_forecast_execution"
CONTROL = BASE / ".outcome_slice_runner"


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha_bytes(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def auth_fingerprint(value: dict[str, Any]) -> str:
    body = {key: value[key] for key in value if key != "authorization_fingerprint"}
    return "sha256:" + hashlib.sha256(canonical(body).encode()).hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(canonical(row) + "\n" for row in rows))


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def fail(message: str) -> None:
    raise SystemExit(message)


class SliceLease:
    def __init__(self, slice_id: str):
        self.path = CONTROL / "leases" / (slice_id + ".json")
        self.fd: int | None = None
        self.record: dict[str, Any] | None = None

    def acquire(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        for _ in range(2):
            try:
                self.fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                self.record = {"slice_id": self.path.stem, "pid": os.getpid(), "status": "ACTIVE", "acquired_ts": now(), "lease_version": 1}
                os.write(self.fd, (canonical(self.record) + "\n").encode())
                return
            except FileExistsError:
                try:
                    current = json.loads(self.path.read_text())
                except Exception:
                    fail("SLICE_LEASE_CORRUPT")
                pid = current.get("pid")
                active = current.get("status") == "ACTIVE" and isinstance(pid, int)
                alive = active
                if active:
                    try:
                        os.kill(pid, 0)
                    except OSError:
                        alive = False
                if alive:
                    fail("SLICE_LEASE_CONTENTION")
                stale = self.path.with_suffix(self.path.suffix + ".stale-" + str(int(time.time())))
                self.path.rename(stale)
        fail("SLICE_LEASE_ACQUIRE_FAILED")

    def release(self) -> None:
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None
        if self.path.exists() and self.record:
            released = dict(self.record)
            released.update({"status": "RELEASED", "released_ts": now()})
            released_path = self.path.with_suffix(self.path.suffix + ".released-" + str(os.getpid()))
            self.path.rename(released_path)
            write_json(released_path, released)


def accepted_dirs(prefix: str, slice_id: str) -> list[Path]:
    return sorted(BASE.glob(f"{prefix}-{slice_id}-*"))


def accepted_collection(slice_id: str, manifest_sha: str) -> Path | None:
    for path in accepted_dirs("PPHB-R1-OUTCOME-COLLECTION", slice_id):
        final = path / "collection_finalization.json"
        decision = path / "collection_decision.json"
        if final.exists() and json.loads(final.read_text()).get("manifest_sha256") == manifest_sha:
            return path
        if decision.exists() and json.loads(decision.read_text()).get("collection_decision", "").endswith("COMPLETE"):
            return path
    # The accepted Slice 001 artifact predates this generalized runner naming.
    legacy = BASE / "PPHB-R1-OUTCOME-COLLECTION-SLICE-001-20260803T001512Z-ceeaad9f41c8"
    return legacy if slice_id == "SLICE-001" and legacy.exists() else None


def accepted_attachment(slice_id: str, manifest_sha: str) -> Path | None:
    label = slice_id.replace("-", "_")
    for path in accepted_dirs("PPHB-R1-OUTCOME-ATTACHMENT", slice_id):
        decision = path / "attachment_decision.json"
        if decision.exists() and json.loads(decision.read_text()).get("decision") == "OUTCOME_" + label + "_ATTACHED_AND_RECONCILED":
            return path
    legacy = BASE / "PPHB-R1-OUTCOME-ATTACHMENT-SLICE-001-20260803T101500Z-5bbe84a70320"
    return legacy if slice_id == "SLICE-001" and legacy.exists() else None


def accepted_evaluation(slice_id: str) -> Path | None:
    label = slice_id.replace("-", "_")
    for path in accepted_dirs("PPHB-R1-OUTCOME-EVALUATION", slice_id):
        decision = path / "evaluation_decision.json"
        if decision.exists() and json.loads(decision.read_text()).get("decision") == "OUTCOME_" + label + "_MINIMAL_EVALUATION_COMPLETE":
            return path
    legacy = BASE / "PPHB-R1-OUTCOME-EVALUATION-SLICE-001-20260803T103000Z-4f8c2b9a6d10"
    return legacy if slice_id == "SLICE-001" and legacy.exists() else None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--authorization", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--expected-manifest-sha", required=True)
    parser.add_argument("--slice-id", required=True)
    parser.add_argument("--max-apps-script-reads", type=int)
    parser.add_argument("--max-market-data-attempts", type=int)
    parser.add_argument("--max-total-external-requests", type=int)
    parser.add_argument("--retry-policy")
    parser.add_argument("--google-write-ceiling", type=int)
    parser.add_argument("--expected-contract")
    parser.add_argument("--expected-schema")
    parser.add_argument("--google-token-env")
    parser.add_argument("--collect", action="store_true")
    parser.add_argument("--attach", action="store_true")
    parser.add_argument("--evaluate", action="store_true")
    parser.add_argument("--offline-fixture", action="store_true", help="Validate accepted local artifacts without executing a stage.")
    parser.add_argument("--run-id")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    auth = json.loads(args.authorization.read_text())
    if auth.get("authorization_fingerprint") != auth_fingerprint(auth):
        fail("AUTHORIZATION_FINGERPRINT_MISMATCH")
    if auth.get("slice_id") != args.slice_id or Path(auth.get("manifest_path", "")).resolve() != args.manifest.resolve():
        fail("AUTHORIZATION_IDENTITY_CONFLICT")
    if auth.get("manifest_sha256") != args.expected_manifest_sha or sha_bytes(args.manifest) != args.expected_manifest_sha:
        fail("MANIFEST_HASH_CONFLICT")
    stages = [stage for stage, selected in (("collect", args.collect), ("attach", args.attach), ("evaluate", args.evaluate)) if selected]
    permitted = set(auth.get("permitted_stages", []))
    if any(stage not in permitted for stage in stages):
        fail("STAGE_NOT_AUTHORIZED")
    ceilings = auth.get("ceilings", {})
    checks = {
        "max_apps_script_reads": args.max_apps_script_reads,
        "max_market_data_attempts": args.max_market_data_attempts,
        "max_total_external_requests": args.max_total_external_requests,
        "google_write_ceiling": args.google_write_ceiling,
    }
    for key, supplied in checks.items():
        if supplied is not None and supplied != ceilings.get(key):
            fail("AUTHORIZATION_CEILING_CONFLICT:" + key)
    for key, supplied, auth_key in (
        ("retry_policy", args.retry_policy, "retry_policy"),
        ("expected_contract", args.expected_contract, "contract"),
        ("expected_schema", args.expected_schema, "schema"),
        ("google_token_env", args.google_token_env, "google_token_env"),
    ):
        if supplied is not None and supplied != auth.get(auth_key):
            fail("AUTHORIZATION_VALUE_CONFLICT:" + key)
    if args.google_write_ceiling is not None and args.google_write_ceiling < 0:
        fail("GOOGLE_WRITE_CEILING_INVALID")
    run_id = args.run_id or ("PPHB-R1-OUTCOME-SLICE-RUN-" + args.slice_id + "-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + args.expected_manifest_sha[-12:])
    run_dir = CONTROL / "runs" / run_id
    if run_dir.exists():
        fail("RUN_ARTIFACT_ALREADY_EXISTS")
    lease = SliceLease(args.slice_id)
    lease.acquire()
    try:
        collection = accepted_collection(args.slice_id, args.expected_manifest_sha)
        attachment = accepted_attachment(args.slice_id, args.expected_manifest_sha)
        evaluation = accepted_evaluation(args.slice_id)
        if args.collect and collection is not None and not args.offline_fixture:
            fail("COLLECTION_ALREADY_ACCEPTED")
        if args.attach and attachment is not None and not args.offline_fixture:
            fail("ATTACHMENT_ALREADY_ACCEPTED")
        if args.evaluate and evaluation is not None and not args.offline_fixture:
            fail("EVALUATION_ALREADY_ACCEPTED")
        decisions = {"preflight": "OUTCOME_SLICE_PREFLIGHT_PASSED", "requested_stages": stages, "offline_fixture": args.offline_fixture}
        write_json(run_dir / "runner_manifest.json", {"run_id": run_id, "slice_id": args.slice_id, "manifest_path": str(args.manifest), "manifest_sha256": args.expected_manifest_sha, "authorization": str(args.authorization), "requested_stages": stages, "external_requests": 0, "google_writes": 0, "default_preflight_only": not stages, "append_only": True})
        manifest_value = json.loads(args.manifest.read_text())
        episode_rows = manifest_value.get("episode_manifest", [])
        if len(episode_rows) != 12 or len({row.get("episode_id") for row in episode_rows}) != 12:
            fail("MANIFEST_EPISODE_RESERVATION_SCOPE_CONFLICT")
        write_jsonl(run_dir / "stage_episode_reservations.jsonl", [
            {"slice_id": args.slice_id, "stage": stage, "episode_id": row["episode_id"], "reservation_state": "RESERVED", "prior_attempt_count": 0, "external_request_allowed": stage == "collect"}
            for stage in stages for row in episode_rows
        ])
        dispatch_state = {stage: "REQUEST_NOT_SENT" for stage in stages}
        write_json(run_dir / "dispatch_state.json", dispatch_state)
        if args.offline_fixture:
            if args.collect and collection is None: fail("COLLECTION_FIXTURE_NOT_FOUND")
            if args.attach and attachment is None: fail("ATTACHMENT_FIXTURE_NOT_FOUND")
            if args.evaluate and evaluation is None: fail("EVALUATION_FIXTURE_NOT_FOUND")
            decisions["collect"] = "OUTCOME_SLICE_COLLECTION_COMPLETE" if args.collect else None
            decisions["attach"] = "OUTCOME_SLICE_ATTACHMENT_COMPLETE" if args.attach else None
            decisions["evaluate"] = "OUTCOME_SLICE_EVALUATION_COMPLETE" if args.evaluate else None
            decisions["fixture_validation"] = {"collection": str(collection) if collection else None, "attachment": str(attachment) if attachment else None, "evaluation": str(evaluation) if evaluation else None}
            for stage in stages:
                dispatch_state[stage] = "FIXTURE_VALIDATED"
        else:
            env = os.environ.copy()
            env.update({"PRESIGNAL_OUTCOME_SLICE_ID": args.slice_id, "PRESIGNAL_OUTCOME_MANIFEST_PATH": str(args.manifest), "PRESIGNAL_OUTCOME_EXPECTED_MANIFEST_SHA": args.expected_manifest_sha, "PRESIGNAL_OUTCOME_MAX_GOOGLE_READS": str(ceilings["max_apps_script_reads"]), "PRESIGNAL_OUTCOME_MAX_PROVIDER_ATTEMPTS": str(ceilings["max_market_data_attempts"]), "PRESIGNAL_OUTCOME_MAX_TOTAL_EXTERNAL": str(ceilings["max_total_external_requests"])})
            if args.collect:
                dispatch_state["collect"] = "REQUEST_SEND_STARTED"
                write_json(run_dir / "dispatch_state.json", dispatch_state)
                try:
                    result = subprocess.run([sys.executable, str(ROOT / "automation" / "collect_presignal_v21_outcome_slice_001.py")], cwd=ROOT, env=env, text=True)
                except KeyboardInterrupt:
                    dispatch_state["collect"] = "REMOTE_STATE_UNKNOWN"
                    write_json(run_dir / "dispatch_state.json", dispatch_state)
                    fail("REMOTE_STATE_UNKNOWN_REQUIRES_GOVERNANCE")
                if result.returncode: fail("OUTCOME_SLICE_COLLECTION_BLOCKED")
                dispatch_state["collect"] = "COMPLETE"
                decisions["collect"] = "OUTCOME_SLICE_COLLECTION_COMPLETE"
            if args.attach:
                collection = accepted_collection(args.slice_id, args.expected_manifest_sha)
                if collection is None: fail("COLLECTION_ARTIFACT_REQUIRED")
                env["PRESIGNAL_OUTCOME_COLLECTION_RUN"] = collection.name
                attach_id = "PPHB-R1-OUTCOME-ATTACHMENT-" + args.slice_id + "-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + args.expected_manifest_sha[-12:]
                result = subprocess.run([sys.executable, str(ROOT / "automation" / "attach_presignal_v21_outcome_slice_001.py"), "--run-id", attach_id], cwd=ROOT, env=env, text=True)
                if result.returncode: fail("OUTCOME_SLICE_ATTACHMENT_BLOCKED")
                dispatch_state["attach"] = "COMPLETE"
                decisions["attach"] = "OUTCOME_SLICE_ATTACHMENT_COMPLETE"
            if args.evaluate:
                attachment = accepted_attachment(args.slice_id, args.expected_manifest_sha)
                if attachment is None: fail("ATTACHED_OUTCOME_ARTIFACT_REQUIRED")
                env["PRESIGNAL_OUTCOME_ATTACHMENT_RUN"] = attachment.name
                eval_id = "PPHB-R1-OUTCOME-EVALUATION-" + args.slice_id + "-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + args.expected_manifest_sha[-12:]
                result = subprocess.run([sys.executable, str(ROOT / "automation" / "evaluate_presignal_v21_outcome_slice_001.py"), "--run-id", eval_id], cwd=ROOT, env=env, text=True)
                if result.returncode: fail("OUTCOME_SLICE_EVALUATION_BLOCKED")
                dispatch_state["evaluate"] = "COMPLETE"
                decisions["evaluate"] = "OUTCOME_SLICE_EVALUATION_COMPLETE"
        write_json(run_dir / "dispatch_state.json", dispatch_state)
        write_json(run_dir / "stage_decisions.json", decisions)
        print(json.dumps(decisions, sort_keys=True))
        return 0
    finally:
        lease.release()


if __name__ == "__main__":
    raise SystemExit(main())
