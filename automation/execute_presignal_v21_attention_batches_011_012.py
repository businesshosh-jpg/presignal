#!/usr/bin/env python3
"""Sequentially execute ATTN_BATCH_011 then conditionally ATTN_BATCH_012."""
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

from automation import execute_presignal_v21_attention_batch_011 as batch011
from automation import execute_presignal_v21_attention_batch_012 as batch012

OUTPUT_ROOT = batch011.OUTPUT_ROOT
PLAN_ID = batch011.PLAN_ID


def canonical_json(value: Any) -> str:
    return batch011.batch004.canonical_json(value)


def now() -> str:
    return batch011.batch004.now()


def write_json(path: Path, value: Any) -> None:
    batch011.batch004.write_json(path, value)


def materialize_run(output_root: Path, fixed_timestamp: str | None = None) -> Path:
    ts = fixed_timestamp or now()
    seed = {"plan_id": PLAN_ID, "move": "ATTENTION_BATCHES_011_012", "timestamp": ts}
    run_id = (
        "PPHB-R1-ATTENTION-EXECUTION-BATCHES-011-012-"
        + ts.replace(":", "").replace("-", "")
        + "-"
        + hashlib.sha256(canonical_json(seed).encode("utf-8")).hexdigest()[:12]
    )
    return output_root / run_id


def shared_failure(result: Mapping[str, Any]) -> tuple[bool, str]:
    decision = result["decision"]
    reconciliation = result["reconciliation"]
    if decision["execution_status"].endswith("_BLOCKED"):
        return True, "BATCH_011_BLOCKED"
    if decision["provider_authority_decision"] == "PROVIDER_AUTHORITY_NOT_REACHED":
        return True, "PROVIDER_AUTHORITY_NOT_REACHED"
    if decision["contract_decision"] == "EXECUTION_ENVIRONMENT_FAILURE":
        return True, "EXECUTION_ENVIRONMENT_FAILURE"
    if reconciliation.get("unexpected_calls", 0) > 0:
        return True, "UNEXPECTED_CALLS_PRESENT"
    if reconciliation.get("duplicate_successful_calls", 0) > 0:
        return True, "DUPLICATE_SUCCESSFUL_CALLS_PRESENT"
    return False, "NO_SHARED_FAILURE"


def continuation_decision(batch_011_result: Mapping[str, Any]) -> tuple[str, str]:
    is_shared, reason = shared_failure(batch_011_result)
    if is_shared:
        if reason in {"BATCH_011_BLOCKED", "EXECUTION_ENVIRONMENT_FAILURE", "PROVIDER_AUTHORITY_NOT_REACHED"}:
            return "STOP_BEFORE_ATTENTION_BATCH_012_SHARED_FAILURE", reason
        return "STOP_BEFORE_ATTENTION_BATCH_012_GOVERNANCE_FAILURE", reason
    return "PROCEED_TO_ATTENTION_BATCH_012", reason


def initialize_move_run(run_dir: Path) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    write_json(
        run_dir / "run_manifest.json",
        {
            "move": "ATTENTION_BATCHES_011_012",
            "plan_id": PLAN_ID,
            "authorized_batches": ["ATTN_BATCH_011", "ATTN_BATCH_012"],
            "maximum_authorized_calls": 24,
        },
    )
    write_json(
        run_dir / "governing_artifact_manifest.json",
        {
            "plan_id": PLAN_ID,
            "batch_011_expected_start_head": batch011.EXPECTED_START_HEAD,
            "batch_012_expected_start_head": batch012.EXPECTED_START_HEAD,
        },
    )
    write_json(
        run_dir / "authorized_batch_manifest.json",
        {
            "authorized_batches": [
                {"batch_id": "ATTN_BATCH_011", "authorized_calls": 12, "call_ids": [row["call_id"] for row in batch011.load_batch_calls()]},
                {"batch_id": "ATTN_BATCH_012", "authorized_calls": 12, "call_ids": [row["call_id"] for row in batch012.load_batch_calls()]},
            ],
            "maximum_total_calls": 24,
        },
    )


def summarize_failures(result: Mapping[str, Any]) -> dict[str, int]:
    r = result["reconciliation"]
    return {
        "failed_transport_calls": r["failed_transport_calls"],
        "failed_provider_calls": r["failed_provider_calls"],
        "failed_provider_authority_calls": r["failed_provider_authority_calls"],
        "failed_parse_calls": r["failed_parse_calls"],
        "failed_completeness_calls": r["completeness_failed_calls"],
        "failed_validation_calls": r["failed_validation_calls"],
    }


def execute_move(
    *,
    output_root: Path = OUTPUT_ROOT,
    batch_output_root: Path = OUTPUT_ROOT,
    fixed_timestamp: str | None = None,
    dispatcher_011: Callable[[Mapping[str, Any]], Mapping[str, Any]] | None = None,
    dispatcher_012: Callable[[Mapping[str, Any]], Mapping[str, Any]] | None = None,
    source_session_loader: Callable[[], tuple[dict[str, Any], dict[str, list[dict[str, Any]]]]] | None = None,
    enforce_head: bool = True,
) -> dict[str, Any]:
    run_dir = materialize_run(output_root=output_root, fixed_timestamp=fixed_timestamp)
    initialize_move_run(run_dir)

    batch_011 = batch011.execute_batch(
        output_root=batch_output_root,
        dispatcher=dispatcher_011,
        fixed_timestamp=fixed_timestamp,
        source_session_loader=source_session_loader,
        enforce_head=enforce_head,
    )
    write_json(
        run_dir / "batch_011_result_reference.json",
        {
            "run_dir": str(batch_011["run_dir"]),
            "decision": batch_011["decision"],
            "reconciliation": batch_011["reconciliation"],
        },
    )

    gate, evidence = continuation_decision(batch_011)
    write_json(
        run_dir / "continuation_gate_decision.json",
        {
            "continuation_decision": gate,
            "evidence": evidence,
            "batch_011_execution_status": batch_011["decision"]["execution_status"],
            "batch_011_contract_decision": batch_011["decision"]["contract_decision"],
            "batch_011_provider_authority_decision": batch_011["decision"]["provider_authority_decision"],
            "batch_011_completeness_decision": batch_011["decision"]["completeness_decision"],
        },
    )

    batch_012: Mapping[str, Any] | None = None
    if gate == "PROCEED_TO_ATTENTION_BATCH_012":
        batch_012 = batch012.execute_batch(
            output_root=batch_output_root,
            dispatcher=dispatcher_012,
            fixed_timestamp=fixed_timestamp,
            source_session_loader=source_session_loader,
            enforce_head=enforce_head,
        )
        write_json(
            run_dir / "batch_012_result_reference.json",
            {
                "run_dir": str(batch_012["run_dir"]),
                "decision": batch_012["decision"],
                "reconciliation": batch_012["reconciliation"],
            },
        )
    else:
        write_json(
            run_dir / "batch_012_result_reference.json",
            {
                "executed": False,
                "decision": "ATTENTION_BATCH_012_NOT_EXECUTED",
                "reason": gate,
            },
        )

    total_attempted = batch_011["reconciliation"]["attempted_calls"] + (batch_012["reconciliation"]["attempted_calls"] if batch_012 else 0)
    total_valid = batch_011["reconciliation"]["successful_valid_calls"] + (batch_012["reconciliation"]["successful_valid_calls"] if batch_012 else 0)
    total_skipped = batch_011["reconciliation"]["skipped_already_successful_calls"] + (batch_012["reconciliation"]["skipped_already_successful_calls"] if batch_012 else 0)
    total_failures = summarize_failures(batch_011)
    if batch_012:
        more = summarize_failures(batch_012)
        for key, value in more.items():
            total_failures[key] += value

    move_status = (
        "ATTENTION_BATCHES_011_012_COMPLETE"
        if batch_012 and batch_011["decision"]["execution_status"].endswith("_COMPLETE") and batch_012["decision"]["execution_status"].endswith("_COMPLETE")
        else "ATTENTION_BATCHES_011_012_STOPPED_AFTER_BATCH_011"
        if gate != "PROCEED_TO_ATTENTION_BATCH_012"
        else "ATTENTION_BATCHES_011_012_PARTIALLY_COMPLETE"
    )
    scaling = (
        "READY_FOR_ATTENTION_BATCHES_013_014"
        if batch_012 and batch_012["decision"]["execution_status"].endswith("_COMPLETE")
        else "REPAIR_BEFORE_FURTHER_ATTENTION_EXECUTION"
        if gate != "PROCEED_TO_ATTENTION_BATCH_012"
        else "RETRY_FAILED_CALLS_REQUIRES_AUTHORIZATION"
    )

    move_reconciliation = {
        "authorized_batches": 2,
        "executed_batches": 2 if batch_012 else 1,
        "total_authorized_calls": 24,
        "total_attempted_provider_calls": total_attempted,
        "total_successful_valid_calls": total_valid,
        "total_skipped_already_successful_calls": total_skipped,
        "total_unexpected_calls": batch_011["reconciliation"]["unexpected_calls"] + (batch_012["reconciliation"]["unexpected_calls"] if batch_012 else 0),
        "total_duplicate_successful_calls": batch_011["reconciliation"]["duplicate_successful_calls"] + (batch_012["reconciliation"]["duplicate_successful_calls"] if batch_012 else 0),
        "continuation_gate_result": gate,
        "batch_011_decision": batch_011["decision"]["execution_status"],
        "batch_012_decision": batch_012["decision"]["execution_status"] if batch_012 else "ATTENTION_BATCH_012_NOT_EXECUTED",
        "cumulative_validated_attention_calls": 120 + total_valid,
        "remaining_attention_calls": 204 - (120 + total_valid),
        **total_failures,
    }
    write_json(run_dir / "move_reconciliation.json", move_reconciliation)
    write_json(run_dir / "move_summary.json", move_reconciliation)
    move_decision = {"move_status": move_status, "scaling_decision": scaling}
    write_json(run_dir / "move_decision.json", move_decision)

    return {
        "run_dir": run_dir,
        "batch_011": batch_011,
        "batch_012": batch_012,
        "continuation_gate": gate,
        "continuation_evidence": evidence,
        "move_reconciliation": move_reconciliation,
        "move_decision": move_decision,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, default=OUTPUT_ROOT)
    parser.add_argument("--fixed-timestamp")
    args = parser.parse_args(argv)
    result = execute_move(output_root=args.output_root, batch_output_root=args.output_root, fixed_timestamp=args.fixed_timestamp)
    print(
        json.dumps(
            {
                "run_dir": str(result["run_dir"]),
                "move_status": result["move_decision"]["move_status"],
                "continuation_gate": result["continuation_gate"],
                "total_attempted_provider_calls": result["move_reconciliation"]["total_attempted_provider_calls"],
                "total_successful_valid_calls": result["move_reconciliation"]["total_successful_valid_calls"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
