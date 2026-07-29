#!/usr/bin/env python3
"""Execute or fail-closed ATTN_BATCH_003 from the frozen Attention execution plan."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Callable, Mapping

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from automation import execute_presignal_v21_attention_batch_001 as base

ROOT = base.ROOT
PLAN_ID = base.PLAN_ID
PLAN_ROOT = base.PLAN_ROOT
OUTPUT_ROOT = base.OUTPUT_ROOT
BATCH_ID = "ATTN_BATCH_003"
EXPECTED_CALL_COUNT = 12
GOVERNING_BATCH_001_CLOSURE_ID = "PPHB-R1-ATTENTION-BATCH-001-CLOSED-20260729T035345Z-e3bc0c2909ca"
GOVERNING_BATCH_002_CLOSURE_ID = "PPHB-R1-ATTENTION-BATCH-002-CLOSED-20260729T044448Z-97d9ec4cf579"


def canonical_json(value: Any) -> str:
    return base.canonical_json(value)


def now() -> str:
    return base.now()


def write_json(path: Path, value: Any) -> None:
    base.write_json(path, value)


def journal_event(path: Path, event: str, **extra: Any) -> None:
    base.journal_event(path, event, **extra)


def load_batch_calls() -> list[dict[str, Any]]:
    calls = base.load_batch_calls(BATCH_ID)
    if len(calls) != EXPECTED_CALL_COUNT:
        raise base.AttentionBatchError("BATCH_003_CALL_COUNT_MISMATCH")
    prior_ids = {row["call_id"] for row in base.load_batch_calls(base.BATCH_ID)}
    prior_ids.update(row["call_id"] for row in __import__("automation.execute_presignal_v21_attention_batch_002", fromlist=["load_batch_calls"]).load_batch_calls())
    overlap = [row["call_id"] for row in calls if row["call_id"] in prior_ids]
    if overlap:
        raise base.AttentionBatchError("BATCH_003_OVERLAPS_PRIOR_BATCH:" + ",".join(overlap))
    return calls


def materialize_run(
    *,
    output_root: Path,
    fixed_timestamp: str | None = None,
    existing_run_dir: Path | None = None,
) -> Path:
    if existing_run_dir is not None:
        return existing_run_dir
    ts = fixed_timestamp or now()
    seed = {"plan_id": PLAN_ID, "batch_id": BATCH_ID, "timestamp": ts}
    run_id = (
        "PPHB-R1-ATTENTION-EXECUTION-BATCH-003-"
        + ts.replace(":", "").replace("-", "")
        + "-"
        + hashlib.sha256(canonical_json(seed).encode("utf-8")).hexdigest()[:12]
    )
    return output_root / run_id


def initialize_run_files(
    run_dir: Path,
    batch_calls: list[dict[str, Any]],
    fingerprint_observations: Mapping[str, str],
    contract: Mapping[str, Any],
    source_sessions: Mapping[str, Any],
    source_members: Mapping[str, list[dict[str, Any]]],
) -> None:
    base.initialize_run_files(
        run_dir,
        batch_calls,
        fingerprint_observations,
        contract,
        source_sessions,
        source_members,
    )
    write_json(
        run_dir / "run_manifest.json",
        {
            **base.read_json(run_dir / "run_manifest.json"),
            "governing_batch_001_closure_id": GOVERNING_BATCH_001_CLOSURE_ID,
            "governing_batch_002_closure_id": GOVERNING_BATCH_002_CLOSURE_ID,
            "authorized_batch_id": BATCH_ID,
            "maximum_authorized_calls": EXPECTED_CALL_COUNT,
            "predecessor_run_id": None,
            "predecessor_attempted_calls": None,
            "rerun_reason": None,
        },
    )
    write_json(
        run_dir / "batch_execution_contract.json",
        {
            "governing_plan_id": PLAN_ID,
            "governing_batch_001_closure_id": GOVERNING_BATCH_001_CLOSURE_ID,
            "governing_batch_002_closure_id": GOVERNING_BATCH_002_CLOSURE_ID,
            "batch_id": BATCH_ID,
            "authorized_call_count": EXPECTED_CALL_COUNT,
            "authorized_call_identities": [row["call_id"] for row in batch_calls],
            "provider_model_routes": dict(base.PROVIDER_MODELS),
            "canonical_attention_contract": "session_attention_map",
            "identity_normalization_rules": "historical Attention provider authority binding plus previously validated narrow compatibility rules",
            "raw_before_parse_requirement": True,
            "retry_policy": "no automatic retry for success or failure within Batch 003",
            "resume_policy": "validated terminal call states skip repeat dispatch",
            "immutability_rules": "append-only run artifacts only; no matrix update in this Move",
        },
    )


def summarize_run(run_dir: Path, batch_calls: list[dict[str, Any]], blocked_reason: str | None = None) -> dict[str, Any]:
    reconciliation = base.summarize_run(run_dir, batch_calls, blocked_reason=blocked_reason)
    reconciliation["authorized_calls"] = EXPECTED_CALL_COUNT
    write_json(run_dir / "batch_reconciliation.json", reconciliation)
    summary = base.read_json(run_dir / "batch_summary.json")
    summary["authorized_calls"] = EXPECTED_CALL_COUNT
    write_json(run_dir / "batch_summary.json", summary)
    return reconciliation


def execute_batch(
    *,
    output_root: Path = OUTPUT_ROOT,
    dispatcher: Callable[[Mapping[str, Any]], Mapping[str, Any]] | None = None,
    fixed_timestamp: str | None = None,
    resume_run_dir: Path | None = None,
    source_session_loader: Callable[[], tuple[dict[str, Any], dict[str, list[dict[str, Any]]]]] | None = None,
) -> dict[str, Any]:
    plan_contract = base.load_plan_contract()
    contract = base.load_runtime_contract()
    fingerprint_observations = base.verify_plan_fingerprints()
    batch_calls = load_batch_calls()
    run_dir = materialize_run(output_root=output_root, fixed_timestamp=fixed_timestamp, existing_run_dir=resume_run_dir)

    credential_status = "SKIPPED_FOR_TEST_DISPATCH" if dispatcher is not None else None
    blocked_reason = None
    if dispatcher is None:
        try:
            preflight = base.preflight_credentials()
            credential_status = preflight["credential_route_status"]
        except Exception as exc:
            blocked_reason = str(exc)
            credential_status = type(exc).__name__
            initialize_run_files(run_dir, batch_calls, fingerprint_observations, contract, {}, {})
            journal_event(run_dir / "operation_journal.jsonl", "BATCH_STARTED", batch_id=BATCH_ID, authorized_calls=EXPECTED_CALL_COUNT)
            journal_event(run_dir / "operation_journal.jsonl", "BATCH_BLOCKED", batch_id=BATCH_ID, reason=blocked_reason)
            reconciliation = summarize_run(run_dir, batch_calls, blocked_reason=blocked_reason)
            decision = {
                "execution_status": "ATTENTION_BATCH_003_BLOCKED",
                "contract_decision": "EXECUTION_ENVIRONMENT_FAILURE",
                "provider_authority_decision": "PROVIDER_AUTHORITY_NOT_REACHED",
                "resume_decision": "RESUME_PROTECTION_VALIDATED",
                "scaling_decision": "REPAIR_BEFORE_BATCH_004",
                "blocked_reason": blocked_reason,
                "credential_route_status": credential_status,
                "plan_contract_identity": plan_contract["attention_output_contract"]["object"],
                "runtime_contract_version": contract["contract_version"],
            }
            base.update_run_manifest(run_dir / "run_manifest.json", provider_calls_executed=0)
            write_json(run_dir / "batch_decision.json", decision)
            return {"run_dir": run_dir, "batch_calls": batch_calls, "decision": decision, "reconciliation": reconciliation}

    loader = source_session_loader or base.read_source_sessions
    source_sessions, source_members = loader()
    for call in batch_calls:
        if call["source_session_id"] not in source_sessions:
            raise base.AttentionBatchError("SOURCE_SESSION_MISSING:" + call["source_session_id"])
    initialize_run_files(run_dir, batch_calls, fingerprint_observations, contract, source_sessions, source_members)
    journal_event(run_dir / "operation_journal.jsonl", "BATCH_STARTED", batch_id=BATCH_ID, authorized_calls=EXPECTED_CALL_COUNT)

    actual_dispatcher = dispatcher or base.live_dispatch
    for call in batch_calls:
        session = source_sessions[call["source_session_id"]]
        members = source_members[call["source_session_id"]]
        base.execute_call(
            run_dir=run_dir,
            call=call,
            session=session,
            members=members,
            contract=contract,
            dispatcher=actual_dispatcher,
        )
    journal_event(run_dir / "operation_journal.jsonl", "BATCH_COMPLETED", batch_id=BATCH_ID)
    reconciliation = summarize_run(run_dir, batch_calls)
    successful = reconciliation["successful_valid_calls"]
    failures = (
        reconciliation["failed_transport_calls"]
        + reconciliation["failed_provider_calls"]
        + reconciliation["failed_parse_calls"]
        + reconciliation["failed_validation_calls"]
        + reconciliation["failed_provider_authority_calls"]
    )
    base.update_run_manifest(run_dir / "run_manifest.json", provider_calls_executed=reconciliation["attempted_calls"])
    if failures == 0:
        contract_decision = "ALL_BATCH_RESULTS_VALID"
        provider_authority_decision = "ALL_PROVIDER_IDENTITIES_AUTHORITATIVELY_BOUND"
        scaling_decision = "READY_FOR_ATTENTION_BATCH_004"
    elif successful == 0:
        contract_decision = "LIVE_ATTENTION_CONTRACT_FAILURE"
        provider_authority_decision = "PROVIDER_AUTHORITY_FAILURES_PRESENT" if reconciliation["failed_provider_authority_calls"] else "PROVIDER_AUTHORITY_NOT_REACHED"
        scaling_decision = "REPAIR_BEFORE_BATCH_004"
    else:
        contract_decision = "VALID_RESULTS_WITH_FAILED_CALLS"
        provider_authority_decision = "PROVIDER_AUTHORITY_FAILURES_PRESENT" if reconciliation["failed_provider_authority_calls"] else "ALL_PROVIDER_IDENTITIES_AUTHORITATIVELY_BOUND"
        scaling_decision = "RETRY_FAILED_BATCH_003_CALLS_REQUIRES_AUTHORIZATION"
    decision = {
        "execution_status": "ATTENTION_BATCH_003_COMPLETE" if successful == EXPECTED_CALL_COUNT else "ATTENTION_BATCH_003_PARTIALLY_COMPLETE",
        "contract_decision": contract_decision,
        "provider_authority_decision": provider_authority_decision,
        "resume_decision": "RESUME_PROTECTION_VALIDATED",
        "scaling_decision": scaling_decision,
    }
    write_json(run_dir / "batch_decision.json", decision)
    return {"run_dir": run_dir, "batch_calls": batch_calls, "decision": decision, "reconciliation": reconciliation}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, default=OUTPUT_ROOT)
    parser.add_argument("--fixed-timestamp")
    args = parser.parse_args(argv)
    result = execute_batch(output_root=args.output_root, fixed_timestamp=args.fixed_timestamp)
    print(
        json.dumps(
            {
                "run_dir": str(result["run_dir"]),
                "execution_status": result["decision"]["execution_status"],
                "attempted_calls": result["reconciliation"]["attempted_calls"],
                "successful_valid_calls": result["reconciliation"]["successful_valid_calls"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
