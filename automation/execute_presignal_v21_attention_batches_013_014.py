#!/usr/bin/env python3
"""Sequentially execute ATTN_BATCH_013 then conditionally ATTN_BATCH_014."""
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

from automation import execute_presignal_v21_attention_batch_013 as batch013
from automation import execute_presignal_v21_attention_batch_014 as batch014

OUTPUT_ROOT = batch013.OUTPUT_ROOT
PLAN_ID = batch013.PLAN_ID


def canonical_json(value: Any) -> str:
    return batch013.batch004.canonical_json(value)


def now() -> str:
    return batch013.batch004.now()


def write_json(path: Path, value: Any) -> None:
    batch013.batch004.write_json(path, value)


def materialize_run(output_root: Path, fixed_timestamp: str | None = None) -> Path:
    ts = fixed_timestamp or now()
    seed = {"plan_id": PLAN_ID, "move": "ATTENTION_BATCHES_013_014", "timestamp": ts}
    run_id = (
        "PPHB-R1-ATTENTION-EXECUTION-BATCHES-013-014-"
        + ts.replace(":", "").replace("-", "")
        + "-"
        + hashlib.sha256(canonical_json(seed).encode("utf-8")).hexdigest()[:12]
    )
    return output_root / run_id


def shared_failure(result: Mapping[str, Any]) -> tuple[bool, str]:
    decision = result["decision"]
    reconciliation = result["reconciliation"]
    if decision["execution_status"].endswith("_BLOCKED"):
        return True, "BATCH_013_BLOCKED"
    if decision["provider_authority_decision"] == "PROVIDER_AUTHORITY_NOT_REACHED":
        return True, "PROVIDER_AUTHORITY_NOT_REACHED"
    if decision["contract_decision"] == "EXECUTION_ENVIRONMENT_FAILURE":
        return True, "EXECUTION_ENVIRONMENT_FAILURE"
    if reconciliation.get("unexpected_calls", 0) > 0:
        return True, "UNEXPECTED_CALLS_PRESENT"
    if reconciliation.get("duplicate_successful_calls", 0) > 0:
        return True, "DUPLICATE_SUCCESSFUL_CALLS_PRESENT"
    return False, "NO_SHARED_FAILURE"


def continuation_decision(batch_013_result: Mapping[str, Any]) -> tuple[str, str]:
    is_shared, reason = shared_failure(batch_013_result)
    if is_shared:
        if reason in {"BATCH_013_BLOCKED", "EXECUTION_ENVIRONMENT_FAILURE", "PROVIDER_AUTHORITY_NOT_REACHED"}:
            return "STOP_BEFORE_ATTENTION_BATCH_014_SHARED_FAILURE", reason
        return "STOP_BEFORE_ATTENTION_BATCH_014_GOVERNANCE_FAILURE", reason
    return "PROCEED_TO_ATTENTION_BATCH_014", reason


def initialize_move_run(run_dir: Path) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    write_json(
        run_dir / "run_manifest.json",
        {
            "move": "ATTENTION_BATCHES_013_014",
            "plan_id": PLAN_ID,
            "authorized_batches": ["ATTN_BATCH_013", "ATTN_BATCH_014"],
            "maximum_authorized_calls": 24,
        },
    )
    write_json(
        run_dir / "governing_artifact_manifest.json",
        {
            "plan_id": PLAN_ID,
            "batch_013_expected_start_head": batch013.EXPECTED_START_HEAD,
            "batch_014_expected_start_head": batch014.EXPECTED_START_HEAD,
            "governing_batches_011_012_coordination_id": batch013.GOVERNING_BATCHES_011_012_COORDINATION_ID,
            "governing_batch_011_execution_id": batch013.GOVERNING_BATCH_011_EXECUTION_ID,
            "governing_batch_012_execution_id": batch013.GOVERNING_BATCH_012_EXECUTION_ID,
        },
    )
    write_json(
        run_dir / "authorized_batch_manifest.json",
        {
            "authorized_batches": [
                {"batch_id": "ATTN_BATCH_013", "authorized_calls": 12, "call_ids": [row["call_id"] for row in batch013.load_batch_calls()]},
                {"batch_id": "ATTN_BATCH_014", "authorized_calls": 12, "call_ids": [row["call_id"] for row in batch014.load_batch_calls()]},
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
    dispatcher_013: Callable[[Mapping[str, Any]], Mapping[str, Any]] | None = None,
    dispatcher_014: Callable[[Mapping[str, Any]], Mapping[str, Any]] | None = None,
    source_session_loader: Callable[[], tuple[dict[str, Any], dict[str, list[dict[str, Any]]]]] | None = None,
    enforce_head: bool = True,
) -> dict[str, Any]:
    run_dir = materialize_run(output_root=output_root, fixed_timestamp=fixed_timestamp)
    initialize_move_run(run_dir)

    batch_013 = batch013.execute_batch(
        output_root=batch_output_root,
        dispatcher=dispatcher_013,
        fixed_timestamp=fixed_timestamp,
        source_session_loader=source_session_loader,
        enforce_head=enforce_head,
    )
    write_json(
        run_dir / "batch_013_result_reference.json",
        {
            "run_dir": str(batch_013["run_dir"]),
            "decision": batch_013["decision"],
            "reconciliation": batch_013["reconciliation"],
        },
    )

    gate, evidence = continuation_decision(batch_013)
    write_json(
        run_dir / "continuation_gate_decision.json",
        {
            "continuation_decision": gate,
            "evidence": evidence,
            "batch_013_execution_status": batch_013["decision"]["execution_status"],
            "batch_013_contract_decision": batch_013["decision"]["contract_decision"],
            "batch_013_provider_authority_decision": batch_013["decision"]["provider_authority_decision"],
            "batch_013_completeness_decision": batch_013["decision"]["completeness_decision"],
        },
    )

    batch_014: Mapping[str, Any] | None = None
    if gate == "PROCEED_TO_ATTENTION_BATCH_014":
        batch_014 = batch014.execute_batch(
            output_root=batch_output_root,
            dispatcher=dispatcher_014,
            fixed_timestamp=fixed_timestamp,
            source_session_loader=source_session_loader,
            enforce_head=enforce_head,
        )
        write_json(
            run_dir / "batch_014_result_reference.json",
            {
                "run_dir": str(batch_014["run_dir"]),
                "decision": batch_014["decision"],
                "reconciliation": batch_014["reconciliation"],
            },
        )
    else:
        write_json(
            run_dir / "batch_014_result_reference.json",
            {
                "executed": False,
                "decision": "ATTENTION_BATCH_014_NOT_EXECUTED",
                "reason": gate,
            },
        )

    total_attempted = batch_013["reconciliation"]["attempted_calls"] + (batch_014["reconciliation"]["attempted_calls"] if batch_014 else 0)
    total_valid = batch_013["reconciliation"]["successful_valid_calls"] + (batch_014["reconciliation"]["successful_valid_calls"] if batch_014 else 0)
    total_skipped = batch_013["reconciliation"]["skipped_already_successful_calls"] + (batch_014["reconciliation"]["skipped_already_successful_calls"] if batch_014 else 0)
    total_failures = summarize_failures(batch_013)
    if batch_014:
        more = summarize_failures(batch_014)
        for key, value in more.items():
            total_failures[key] += value

    if batch_014 and batch_013["decision"]["execution_status"].endswith("_COMPLETE") and batch_014["decision"]["execution_status"].endswith("_COMPLETE"):
        move_status = "ATTENTION_BATCHES_013_014_COMPLETE"
    elif gate != "PROCEED_TO_ATTENTION_BATCH_014":
        move_status = "ATTENTION_BATCHES_013_014_STOPPED_AFTER_BATCH_013"
    else:
        move_status = "ATTENTION_BATCHES_013_014_PARTIALLY_COMPLETE"

    if batch_014 and batch_014["decision"]["execution_status"].endswith("_COMPLETE"):
        scaling = "READY_FOR_ATTENTION_BATCHES_015_016"
    elif gate != "PROCEED_TO_ATTENTION_BATCH_014":
        scaling = "REPAIR_BEFORE_FURTHER_ATTENTION_EXECUTION"
    else:
        scaling = "RETRY_FAILED_CALLS_REQUIRES_AUTHORIZATION"

    move_reconciliation = {
        "authorized_batches": 2,
        "executed_batches": 2 if batch_014 else 1,
        "total_authorized_calls": 24,
        "total_attempted_provider_calls": total_attempted,
        "total_successful_valid_calls": total_valid,
        "total_skipped_already_successful_calls": total_skipped,
        "total_unexpected_calls": batch_013["reconciliation"]["unexpected_calls"] + (batch_014["reconciliation"]["unexpected_calls"] if batch_014 else 0),
        "total_duplicate_successful_calls": batch_013["reconciliation"]["duplicate_successful_calls"] + (batch_014["reconciliation"]["duplicate_successful_calls"] if batch_014 else 0),
        "continuation_gate_result": gate,
        "batch_013_decision": batch_013["decision"]["execution_status"],
        "batch_014_decision": batch_014["decision"]["execution_status"] if batch_014 else "ATTENTION_BATCH_014_NOT_EXECUTED",
        "cumulative_validated_attention_calls": 144 + total_valid,
        "remaining_attention_calls": 204 - (144 + total_valid),
        **total_failures,
    }
    write_json(run_dir / "move_reconciliation.json", move_reconciliation)
    write_json(run_dir / "move_summary.json", move_reconciliation)
    move_decision = {"move_status": move_status, "scaling_decision": scaling}
    write_json(run_dir / "move_decision.json", move_decision)

    return {
        "run_dir": run_dir,
        "batch_013": batch_013,
        "batch_014": batch_014,
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
