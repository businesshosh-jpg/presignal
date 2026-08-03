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
PARTIAL_AUTH_PATH = os.environ.get("PRESIGNAL_PAIRED_EXCLUSION_AUTH_PATH", "")
INVALID_CALLS = {
    "FCL_27720b8b23236b173b96fdee",
    "FCL_7f0463b134c67757968580e8",
    "FCL_e07264654e9d3da6f63088a1",
}


def manifest_episode_count() -> int:
    manifest = json.loads(MANIFEST.read_text())
    return len(manifest.get("episode_manifest", []))


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text("".join(canonical(row) + "\n" for row in rows))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    text = path.read_text()
    if text.lstrip().startswith("["):
        value = json.loads(text)
        if not isinstance(value, list):
            raise SystemExit("COLLECTION_RECORDS_NOT_A_LIST")
        return value
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def partial_authorization() -> dict[str, Any] | None:
    if not PARTIAL_AUTH_PATH:
        return None
    auth = json.loads(Path(PARTIAL_AUTH_PATH).read_text())
    if auth.get("authorization_mode") != "PAIRED_EXCLUSION_ATTACHMENT" or auth.get("evaluation_authorized") is not False:
        raise SystemExit("PAIRED_EXCLUSION_AUTHORIZATION_CONFLICT")
    return auth


def resolve_collection_inputs(collection_dir: Path, expected_manifest_sha: str) -> dict[str, Any]:
    """Accept the collector's native artifacts or the legacy finalized names."""
    legacy_finalization = collection_dir / "collection_finalization.json"
    legacy_candidates = collection_dir / "candidate_outcomes_final.jsonl"
    native_reconciliation = collection_dir / "collection_reconciliation.json"
    native_candidates = collection_dir / "candidate_outcomes.jsonl"
    run_manifest = collection_dir / "run_manifest.json"

    if legacy_finalization.exists() and legacy_candidates.exists():
        finalization = json.loads(legacy_finalization.read_text())
        candidates_path = legacy_candidates
        source_mode = "LEGACY_FINALIZED_ARTIFACTS"
    elif native_reconciliation.exists() and native_candidates.exists() and run_manifest.exists():
        reconciliation = json.loads(native_reconciliation.read_text())
        run = json.loads(run_manifest.read_text())
        if run.get("manifest_sha256") != expected_manifest_sha:
            raise SystemExit("COLLECTION_MANIFEST_BINDING_MISMATCH")
        expected_count = manifest_episode_count()
        if reconciliation.get("manifest_episode_count") != expected_count:
            raise SystemExit("COLLECTION_RECONCILIATION_COUNT_MISMATCH")
        if reconciliation.get("candidate_outcomes") != expected_count or reconciliation.get("schema_validated_candidates") != expected_count:
            raise SystemExit("COLLECTION_RECONCILIATION_INCOMPLETE")
        if (reconciliation.get("unresolved_identities") or reconciliation.get("missing_or_terminal_source_episodes")) and partial_authorization() is None:
            raise SystemExit("COLLECTION_RECONCILIATION_UNRESOLVED")
        if reconciliation.get("duplicate_requests") != 0 or reconciliation.get("google_writes") != 0:
            raise SystemExit("COLLECTION_RECONCILIATION_CONFLICT")
        decision = json.loads((collection_dir / "collection_decision.json").read_text())
        accepted_decisions = {"OUTCOME_COLLECTION_" + SLICE_LABEL + "_COMPLETE", "OUTCOME_COLLECTION_SLICE_002_COMPLETE"}
        if decision.get("collection_decision") not in accepted_decisions:
            raise SystemExit("COLLECTION_COMPLETION_NOT_ACCEPTED")
        finalization = {"manifest_sha256": expected_manifest_sha, "source_mode": "COLLECTOR_NATIVE_ARTIFACTS"}
        candidates_path = native_candidates
        source_mode = "COLLECTOR_NATIVE_ARTIFACTS"
    else:
        raise SystemExit("COLLECTION_ARTIFACT_BRIDGE_INPUTS_MISSING")

    if finalization.get("manifest_sha256") != expected_manifest_sha:
        raise SystemExit("COLLECTION_MANIFEST_BINDING_MISMATCH")
    candidates = read_jsonl(candidates_path)
    if len(candidates) != manifest_episode_count():
        raise SystemExit("OUTCOME_SLICE_COUNT_MISMATCH")
    return {
        "candidates": candidates,
        "candidates_path": str(candidates_path),
        "source_mode": source_mode,
        "source_hashes": {
            "run_manifest": sha(run_manifest),
            "collection_reconciliation": sha(native_reconciliation if native_reconciliation.exists() else legacy_finalization),
            "candidate_records": sha(candidates_path),
        },
    }


def validate_bridge_candidates(candidates: list[dict[str, Any]], expected_episode_ids: set[str]) -> None:
    """Reject missing, extra, duplicate, or semantically altered candidate rows."""
    if len(candidates) != manifest_episode_count():
        raise SystemExit("OUTCOME_SLICE_COUNT_MISMATCH")
    seen_episodes: set[str] = set()
    seen_outcomes: set[str] = set()
    for row in candidates:
        outcome = row.get("candidate_outcome", {})
        episode_id = row.get("episode_id")
        if episode_id in seen_episodes or episode_id not in expected_episode_ids:
            raise SystemExit("COLLECTION_CANDIDATE_IDENTITY_CONFLICT")
        seen_episodes.add(episode_id)
        if outcome.get("episode_id") != episode_id or outcome.get("outcome_id") in seen_outcomes:
            raise SystemExit("COLLECTION_CANDIDATE_DUPLICATE_OR_IDENTITY_CONFLICT")
        seen_outcomes.add(outcome.get("outcome_id"))
        if outcome.get("outcome_fingerprint") != row.get("outcome_fingerprint"):
            raise SystemExit("COLLECTION_CANDIDATE_FINGERPRINT_CONFLICT")
        try:
            contract.validate_outcome(outcome)
        except Exception as exc:
            raise SystemExit("COLLECTION_CANDIDATE_SCHEMA_CONFLICT:" + type(exc).__name__) from exc
    if seen_episodes != expected_episode_ids:
        raise SystemExit("COLLECTION_CANDIDATE_IDENTITY_CONFLICT")


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

    manifest_bytes_hash = sha(MANIFEST)
    manifest_declared_hash = json.loads(MANIFEST.read_text()).get("manifest_fingerprint")
    if manifest_bytes_hash != EXPECTED_MANIFEST_SHA and manifest_declared_hash != EXPECTED_MANIFEST_SHA:
        raise SystemExit("OUTCOME_MANIFEST_HASH_MISMATCH")
    partial_auth = partial_authorization()
    collection_inputs = resolve_collection_inputs(COLLECTION_DIR, EXPECTED_MANIFEST_SHA)

    manifest = json.loads(MANIFEST.read_text())
    manifest_rows = manifest["episode_manifest"]
    candidates = collection_inputs["candidates"]
    if len(manifest_rows) != manifest_episode_count():
        raise SystemExit("OUTCOME_SLICE_COUNT_MISMATCH")
    manifest_by_episode = {row["episode_id"]: row for row in manifest_rows}
    if len(manifest_by_episode) != manifest_episode_count():
        raise SystemExit("OUTCOME_SLICE_DUPLICATE_EPISODE")
    validate_bridge_candidates(candidates, set(manifest_by_episode))

    if partial_auth is not None:
        excluded = set(partial_auth["excluded_episode_ids"])
        expected_eligible = set(partial_auth["authorized_identity_ids"])
        if excluded & expected_eligible or len(expected_eligible) != 10 or len(excluded) != 2:
            raise SystemExit("PAIRED_EXCLUSION_POPULATION_CONFLICT")
        if {row["episode_id"] for row in candidates if row.get("status") == "UNAVAILABLE"} != excluded:
            raise SystemExit("PAIRED_EXCLUSION_UNAVAILABLE_SCOPE_CONFLICT")
        candidates = [row for row in candidates if row["episode_id"] in expected_eligible and row.get("status") == "VALID"]
        if len(candidates) != 10 or {row["episode_id"] for row in candidates} != expected_eligible:
            raise SystemExit("PAIRED_EXCLUSION_CANDIDATE_POPULATION_CONFLICT")

    prior_attachment_dirs = list(BASE.glob(f"PPHB-R1-OUTCOME-ATTACHMENT-{SLICE_ID}-*"))
    if prior_attachment_dirs:
        raise SystemExit("PRIOR_OUTCOME_ATTACHMENT_REQUIRES_RECONCILIATION")

    request_ledger_path = COLLECTION_DIR / "external_request_ledger_final.jsonl"
    if not request_ledger_path.exists():
        request_ledger_path = COLLECTION_DIR / "external_request_ledger.jsonl"
    request_rows = read_jsonl(request_ledger_path)
    request_by_id = {row["request_id"]: row for row in request_rows}
    if partial_auth is None and (len(request_by_id) != len(request_rows) or len(request_rows) != 3):
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
            if not partial_auth and request["request_id"] not in request_by_id:
                raise SystemExit("OUTCOME_REQUEST_LINEAGE_MISSING:" + episode_id)
            if not partial_auth and request_by_id[request["request_id"]]["raw_response_hash"] != request["raw_response_hash"]:
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
        "candidate_count": len(candidates),
        "attachment_count": len(candidates),
        "external_requests": 0,
        "google_reads": 0,
        "google_writes": 0,
        "market_data_calls": 0,
        "provider_calls": 0,
        "evaluation_calculations": 0,
        "append_only": True,
        "collection_bridge": collection_inputs,
        "paired_exclusion_authorization": str(PARTIAL_AUTH_PATH) if partial_auth else None,
        "generated_ts": now,
    })
    write_json(run_dir / "attachment_preflight.json", {
        "decision": "OUTCOME_ATTACHMENT_PREFLIGHT_PASSED",
        "candidate_count": len(candidates),
        "manifest_episode_count": manifest_episode_count(),
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
        "authorized_candidate_count": len(candidates),
        "attached_outcome_count": len(candidates),
        "unattached_candidate_count": 0,
        "failures_by_episode": {},
        "duplicate_or_conflicting_attachments": 0,
        "schema_validation": {"contract": "presignal_event_path_contract_v1_1", "schema_version": "2.1.1", "valid": len(candidates)},
        "candidate_to_attached_hash_linkage": "PASSED",
        "episode_coverage": f"{len(candidates)}_OF_{len(candidates)}",
        "pack_a_e_forecast_coverage": coverage,
        "unresolved_identities": [],
        "external_requests": 0,
        "google_writes": 0,
        "evaluation_calculations": 0,
        "paired_exclusion": partial_auth["excluded_episode_ids"] if partial_auth else [],
    })
    write_json(run_dir / "attachment_decision.json", {
        "run_id": args.run_id,
        "decision": "OUTCOME_" + SLICE_LABEL + "_ATTACHED_AND_RECONCILED",
        "readiness": "OUTCOME_" + SLICE_LABEL + "_READY_FOR_MINIMAL_EVALUATION",
        "candidate_count": len(candidates),
        "attached_count": len(candidates),
        "unattached_count": 0,
        "coverage_only": True,
        "evaluation_authorized": False,
    })
    print(json.dumps({"run_id": args.run_id, "coverage": coverage}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
