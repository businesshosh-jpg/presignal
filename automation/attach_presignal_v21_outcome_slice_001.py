#!/usr/bin/env python3
"""Attach the authorized Outcome slice locally, without evaluation or external access."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from automation import presignal_v21_event_path_contract_v1_1 as contract

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "outputs" / "presignal_v21_full_round_1_forecast_execution"
COLLECTION_RUN = os.environ.get("PRESIGNAL_OUTCOME_COLLECTION_RUN", "PPHB-R1-OUTCOME-COLLECTION-SLICE-001-20260803T001512Z-ceeaad9f41c8")
SLICE_ID = os.environ.get("PRESIGNAL_OUTCOME_SLICE_ID", "SLICE-001")
SLICE_LABEL = SLICE_ID.replace("-", "_")
COLLECTION_DIR = BASE / COLLECTION_RUN
MANIFEST = Path(os.environ.get("PRESIGNAL_OUTCOME_MANIFEST_PATH", str(ROOT / "outputs" / "presignal_v21_full_round_1_forecast_execution" / (
    "PPHB-R1-OUTCOME-AUTHORIZATION-PREPARATION-20260803T090000Z-18cddcdc5477"
) / "next_authorization_draft.json")))
EXPECTED_MANIFEST_SHA = os.environ.get("PRESIGNAL_OUTCOME_EXPECTED_MANIFEST_SHA", "sha256:90765146ec192c58fe841b61b49d239fae321a99b2a73d3f8529ceeaad9f41c8")
INVALID_CALLS = {
    "FCL_27720b8b23236b173b96fdee",
    "FCL_7f0463b134c67757968580e8",
    "FCL_e07264654e9d3da6f63088a1",
}


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text("".join(canonical(row) + "\n" for row in rows))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def utc(value: str) -> str:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def forecast_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for path in sorted(BASE.glob("PPHB-R1-FORECAST-EXECUTION-BATCH-*/batch_call_manifest.jsonl")):
        for row in read_jsonl(path):
            call_id = row.get("forecast_call_id")
            if call_id and call_id not in seen:
                seen.add(call_id)
                rows.append(row)
    return rows


def validate_forecast_coverage(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    episode_ids = {row["episode_id"] for row in candidates}
    rows = [
        row for row in forecast_rows()
        if row.get("episode_id") in episode_ids and row.get("forecast_call_id") not in INVALID_CALLS
    ]
    groups: defaultdict[tuple[str, str], set[str]] = defaultdict(set)
    for row in rows:
        groups[(row["episode_id"], row["historical_cutoff"])].add(row["pack_type"])
    complete = sum(packs == {"PACK_A", "PACK_E"} for packs in groups.values())
    a_only = sum(packs == {"PACK_A"} for packs in groups.values())
    e_only = sum(packs == {"PACK_E"} for packs in groups.values())
    return {
        "valid_forecasts_outcome_covered": len(rows),
        "complete_pack_a_e_pairs_outcome_covered": complete,
        "pack_a_only_valid_forecasts_outcome_covered": a_only,
        "pack_e_only_valid_forecasts_outcome_covered": e_only,
        "forecast_call_ids": sorted(row["forecast_call_id"] for row in rows),
        "invalid_calls_excluded": sorted(INVALID_CALLS),
        "unresolved_pair_keys": sorted(
            {"episode_id": episode, "historical_cutoff": cutoff, "packs": sorted(packs)}
            for (episode, cutoff), packs in groups.items()
            if packs not in ({"PACK_A", "PACK_E"},)
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    run_dir = BASE / args.run_id
    if run_dir.exists():
        raise SystemExit("ATTACHMENT_RUN_ALREADY_EXISTS")

    finalization = json.loads((COLLECTION_DIR / "collection_finalization.json").read_text())
    manifest_bytes_hash = sha(MANIFEST)
    if manifest_bytes_hash != EXPECTED_MANIFEST_SHA:
        raise SystemExit("OUTCOME_MANIFEST_HASH_MISMATCH")
    if finalization["manifest_sha256"] != EXPECTED_MANIFEST_SHA:
        raise SystemExit("COLLECTION_MANIFEST_BINDING_MISMATCH")

    manifest = json.loads(MANIFEST.read_text())
    manifest_rows = manifest["episode_manifest"]
    candidates = read_jsonl(COLLECTION_DIR / "candidate_outcomes_final.jsonl")
    if len(manifest_rows) != 12 or len(candidates) != 12:
        raise SystemExit("OUTCOME_SLICE_COUNT_MISMATCH")
    manifest_by_episode = {row["episode_id"]: row for row in manifest_rows}
    if len(manifest_by_episode) != 12:
        raise SystemExit("OUTCOME_SLICE_DUPLICATE_EPISODE")

    prior_attachment_dirs = list(BASE.glob(f"PPHB-R1-OUTCOME-ATTACHMENT-{SLICE_ID}-*"))
    if prior_attachment_dirs:
        raise SystemExit("PRIOR_OUTCOME_ATTACHMENT_REQUIRES_RECONCILIATION")

    request_rows = read_jsonl(COLLECTION_DIR / "external_request_ledger_final.jsonl")
    request_by_id = {row["request_id"]: row for row in request_rows}
    if len(request_by_id) != len(request_rows) or len(request_rows) != 3:
        raise SystemExit("REQUEST_LINEAGE_NOT_UNIQUE")

    attached: list[dict[str, Any]] = []
    links: list[dict[str, Any]] = []
    seen_outcomes: set[str] = set()
    for row in candidates:
        episode_id = row["episode_id"]
        outcome = row["candidate_outcome"]
        manifest_row = manifest_by_episode.get(episode_id)
        if manifest_row is None or utc(outcome["release_ts"]) != utc(manifest_row["release_ts"]):
            raise SystemExit("OUTCOME_EPISODE_RELEASE_MISMATCH:" + episode_id)
        if outcome["episode_id"] != episode_id or outcome["schema_version"] != "2.1.1":
            raise SystemExit("OUTCOME_IDENTITY_SCHEMA_MISMATCH:" + episode_id)
        if outcome["outcome_id"] in seen_outcomes or row["outcome_fingerprint"] in seen_outcomes:
            raise SystemExit("OUTCOME_DUPLICATE")
        seen_outcomes.update({outcome["outcome_id"], row["outcome_fingerprint"]})
        if outcome["outcome_fingerprint"] != row["outcome_fingerprint"]:
            raise SystemExit("CANDIDATE_FINGERPRINT_FIELD_MISMATCH:" + episode_id)
        contract.validate_outcome(outcome)
        lineage = outcome["source_lineage"]
        if lineage.get("instrument") != "USD/JPY" or not lineage.get("endpoint_deployment"):
            raise SystemExit("OUTCOME_SOURCE_LINEAGE_MISMATCH:" + episode_id)
        for request in lineage.get("request_windows", []):
            if request["request_id"] not in request_by_id:
                raise SystemExit("OUTCOME_REQUEST_LINEAGE_MISSING:" + episode_id)
            if request_by_id[request["request_id"]]["raw_response_hash"] != request["raw_response_hash"]:
                raise SystemExit("OUTCOME_RAW_HASH_MISMATCH:" + episode_id)
        attached_row = {
            "attachment_status": "ATTACHED_LOCAL_APPEND_ONLY",
            "attachment_source_run_id": COLLECTION_RUN,
            "candidate_outcome": outcome,
            "candidate_outcome_fingerprint": outcome["outcome_fingerprint"],
            "episode_id": episode_id,
            "manifest_sha256": EXPECTED_MANIFEST_SHA,
            "outcome_id": outcome["outcome_id"],
        }
        attached.append(attached_row)
        links.append({
            "attachment_status": "ATTACHED_LOCAL_APPEND_ONLY",
            "attached_outcome_hash": outcome["outcome_fingerprint"],
            "candidate_outcome_hash": row["outcome_fingerprint"],
            "candidate_source_collection_run": COLLECTION_RUN,
            "episode_id": episode_id,
            "manifest_sha256": EXPECTED_MANIFEST_SHA,
            "outcome_id": outcome["outcome_id"],
        })

    coverage = validate_forecast_coverage(candidates)
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    run_dir.mkdir(parents=True)
    write_json(run_dir / "run_manifest.json", {
        "run_id": args.run_id,
        "move_type": "OUTCOME_ATTACHMENT_AND_RECONCILIATION_" + SLICE_LABEL,
        "source_collection_run_id": COLLECTION_RUN,
        "manifest_sha256": EXPECTED_MANIFEST_SHA,
        "candidate_count": 12,
        "attachment_count": 12,
        "external_requests": 0,
        "google_reads": 0,
        "google_writes": 0,
        "market_data_calls": 0,
        "provider_calls": 0,
        "evaluation_calculations": 0,
        "append_only": True,
        "generated_ts": now,
    })
    write_json(run_dir / "attachment_preflight.json", {
        "decision": "OUTCOME_ATTACHMENT_PREFLIGHT_PASSED",
        "candidate_count": 12,
        "manifest_episode_count": 12,
        "manifest_sha256": EXPECTED_MANIFEST_SHA,
        "schema_version": "2.1.1",
        "contract": "presignal_event_path_contract_v1_1",
        "identity_checks": "PASSED",
        "timestamp_checks": "PASSED_UTC",
        "hash_checks": "PASSED",
        "source_lineage_checks": "PASSED",
        "duplicate_checks": "PASSED",
        "prior_authoritative_attachment": False,
        "external_access": 0,
    })
    write_jsonl(run_dir / "candidate_to_attachment.jsonl", links)
    write_jsonl(run_dir / "attached_outcomes.jsonl", attached)
    write_json(run_dir / "attachment_reconciliation.json", {
        "authorized_candidate_count": 12,
        "attached_outcome_count": 12,
        "unattached_candidate_count": 0,
        "failures_by_episode": {},
        "duplicate_or_conflicting_attachments": 0,
        "schema_validation": {"contract": "presignal_event_path_contract_v1_1", "schema_version": "2.1.1", "valid": 12},
        "candidate_to_attached_hash_linkage": "PASSED",
        "episode_coverage": "12_OF_12",
        "pack_a_e_forecast_coverage": coverage,
        "unresolved_identities": [],
        "external_requests": 0,
        "google_writes": 0,
        "evaluation_calculations": 0,
    })
    write_json(run_dir / "attachment_decision.json", {
        "run_id": args.run_id,
        "decision": "OUTCOME_" + SLICE_LABEL + "_ATTACHED_AND_RECONCILED",
        "readiness": "OUTCOME_" + SLICE_LABEL + "_READY_FOR_MINIMAL_EVALUATION",
        "candidate_count": 12,
        "attached_count": 12,
        "unattached_count": 0,
        "coverage_only": True,
        "evaluation_authorized": False,
    })
    print(json.dumps({"run_id": args.run_id, "coverage": coverage}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
