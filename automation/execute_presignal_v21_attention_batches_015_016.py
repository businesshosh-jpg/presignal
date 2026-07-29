#!/usr/bin/env python3
"""Sequentially execute ATTN_BATCH_015 then conditionally ATTN_BATCH_016."""
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

from automation import execute_presignal_v21_attention_batch_015 as batch015
from automation import execute_presignal_v21_attention_batch_016 as batch016

OUTPUT_ROOT = batch015.OUTPUT_ROOT
PLAN_ID = batch015.PLAN_ID


def canonical_json(value: Any) -> str:
    return batch015.batch004.canonical_json(value)


def now() -> str:
    return batch015.batch004.now()


def write_json(path: Path, value: Any) -> None:
    batch015.batch004.write_json(path, value)


def materialize_run(output_root: Path, fixed_timestamp: str | None = None) -> Path:
    ts = fixed_timestamp or now()
    seed = {"plan_id": PLAN_ID, "move": "ATTENTION_BATCHES_015_016", "timestamp": ts}
    run_id = (
        "PPHB-R1-ATTENTION-EXECUTION-BATCHES-015-016-"
        + ts.replace(":", "").replace("-", "")
        + "-"
        + hashlib.sha256(canonical_json(seed).encode("utf-8")).hexdigest()[:12]
    )
    return output_root / run_id


def shared_failure(result: Mapping[str, Any]) -> tuple[bool, str]:
    decision = result["decision"]
    reconciliation = result["reconciliation"]
    if decision["execution_status"].endswith("_BLOCKED"):
        return True, "BATCH_015_BLOCKED"
    if decision["provider_authority_decision"] == "PROVIDER_AUTHORITY_NOT_REACHED":
        return True, "PROVIDER_AUTHORITY_NOT_REACHED"
    if decision["contract_decision"] == "EXECUTION_ENVIRONMENT_FAILURE":
        return True, "EXECUTION_ENVIRONMENT_FAILURE"
    if reconciliation.get("unexpected_calls", 0) > 0:
        return True, "UNEXPECTED_CALLS_PRESENT"
    if reconciliation.get("duplicate_successful_calls", 0) > 0:
        return True, "DUPLICATE_SUCCESSFUL_CALLS_PRESENT"
    return False, "NO_SHARED_FAILURE"


def continuation_decision(batch_015_result: Mapping[str, Any]) -> tuple[str, str]:
    is_shared, reason = shared_failure(batch_015_result)
    if is_shared:
        if reason in {"BATCH_015_BLOCKED", "EXECUTION_ENVIRONMENT_FAILURE", "PROVIDER_AUTHORITY_NOT_REACHED"}:
            return "STOP_BEFORE_ATTENTION_BATCH_016_SHARED_FAILURE", reason
        return "STOP_BEFORE_ATTENTION_BATCH_016_GOVERNANCE_FAILURE", reason
    return "PROCEED_TO_ATTENTION_BATCH_016", reason


def initialize_move_run(run_dir: Path) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    write_json(
        run_dir / "run_manifest.json",
        {
            "move": "ATTENTION_BATCHES_015_016",
            "plan_id": PLAN_ID,
            "authorized_batches": ["ATTN_BATCH_015", "ATTN_BATCH_016"],
            "maximum_authorized_calls": 24,
        },
    )
    write_json(
        run_dir / "governing_artifact_manifest.json",
        {
            "plan_id": PLAN_ID,
            "batch_015_expected_start_head": batch015.EXPECTED_START_HEAD,
            "batch_016_expected_start_head": batch016.EXPECTED_START_HEAD,
            "governing_batches_013_014_coordination_id": batch015.GOVERNING_BATCHES_013_014_COORDINATION_ID,
            "governing_batch_013_execution_id": batch015.GOVERNING_BATCH_013_EXECUTION_ID,
            "governing_batch_014_execution_id": batch015.GOVERNING_BATCH_014_EXECUTION_ID,
        },
    )
    write_json(
        run_dir / "authorized_batch_manifest.json",
        {
            "authorized_batches": [
                {"batch_id": "ATTN_BATCH_015", "authorized_calls": 12, "call_ids": [row["call_id"] for row in batch015.load_batch_calls()]},
                {"batch_id": "ATTN_BATCH_016", "authorized_calls": 12, "call_ids": [row["call_id"] for row in batch016.load_batch_calls()]},
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
    dispatcher_015: Callable[[Mapping[str, Any]], Mapping[str, Any]] | None = None,
    dispatcher_016: Callable[[Mapping[str, Any]], Mapping[str, Any]] | None = None,
    source_session_loader: Callable[[], tuple[dict[str, Any], dict[str, list[dict[str, Any]]]]] | None = None,
    enforce_head: bool = True,
) -> dict[str, Any]:
    run_dir = materialize_run(output_root=output_root, fixed_timestamp=fixed_timestamp)
    initialize_move_run(run_dir)

    batch_015 = batch015.execute_batch(
        output_root=batch_output_root,
        dispatcher=dispatcher_015,
        fixed_timestamp=fixed_timestamp,
        source_session_loader=source_session_loader,
        enforce_head=enforce_head,
    )
    write_json(
        run_dir / "batch_015_result_reference.json",
        {
            "run_dir": str(batch_015["run_dir"]),
            "decision": batch_015["decision"],
            "reconciliation": batch_015["reconciliation"],
        },
    )

    gate, evidence = continuation_decision(batch_015)
    write_json(
        run_dir / "continuation_gate_decision.json",
        {
            "continuation_decision": gate,
            "evidence": evidence,
            "batch_015_execution_status": batch_015["decision"]["execution_status"],
            "batch_015_contract_decision": batch_015["decision"]["contract_decision"],
            "batch_015_provider_authority_decision": batch_015["decision"]["provider_authority_decision"],
            "batch_015_completeness_decision": batch_015["decision"]["completeness_decision"],
        },
    )

    batch_016: Mapping[str, Any] | None = None
    if gate == "PROCEED_TO_ATTENTION_BATCH_016":
        batch_016 = batch016.execute_batch(
            output_root=batch_output_root,
            dispatcher=dispatcher_016,
            fixed_timestamp=fixed_timestamp,
            source_session_loader=source_session_loader,
            enforce_head=enforce_head,
        )
        write_json(
            run_dir / "batch_016_result_reference.json",
            {
                "run_dir": str(batch_016["run_dir"]),
                "decision": batch_016["decision"],
                "reconciliation": batch_016["reconciliation"],
            },
        )
    else:
        write_json(
            run_dir / "batch_016_result_reference.json",
            {
                "executed": False,
                "decision": "ATTENTION_BATCH_016_NOT_EXECUTED",
                "reason": gate,
            },
        )

    total_attempted = batch_015["reconciliation"]["attempted_calls"] + (batch_016["reconciliation"]["attempted_calls"] if batch_016 else 0)
    total_valid = batch_015["reconciliation"]["successful_valid_calls"] + (batch_016["reconciliation"]["successful_valid_calls"] if batch_016 else 0)
    total_skipped = batch_015["reconciliation"]["skipped_already_successful_calls"] + (batch_016["reconciliation"]["skipped_already_successful_calls"] if batch_016 else 0)
    total_failures = summarize_failures(batch_015)
    if batch_016:
        more = summarize_failures(batch_016)
        for key, value in more.items():
            total_failures[key] += value

    if batch_016 and batch_015["decision"]["execution_status"].endswith("_COMPLETE") and batch_016["decision"]["execution_status"].endswith("_COMPLETE"):
        move_status = "ATTENTION_BATCHES_015_016_COMPLETE"
    elif gate != "PROCEED_TO_ATTENTION_BATCH_016":
        move_status = "ATTENTION_BATCHES_015_016_STOPPED_AFTER_BATCH_015"
    else:
        move_status = "ATTENTION_BATCHES_015_016_PARTIALLY_COMPLETE"

    if batch_016 and batch_016["decision"]["execution_status"].endswith("_COMPLETE"):
        scaling = "READY_FOR_ATTENTION_BATCH_017"
    elif gate != "PROCEED_TO_ATTENTION_BATCH_016":
        scaling = "REPAIR_BEFORE_FURTHER_ATTENTION_EXECUTION"
    else:
        scaling = "RETRY_FAILED_CALLS_REQUIRES_AUTHORIZATION"

    move_reconciliation = {
        "authorized_batches": 2,
        "executed_batches": 2 if batch_016 else 1,
        "total_authorized_calls": 24,
        "total_attempted_provider_calls": total_attempted,
        "total_successful_valid_calls": total_valid,
        "total_skipped_already_successful_calls": total_skipped,
        "total_unexpected_calls": batch_015["reconciliation"]["unexpected_calls"] + (batch_016["reconciliation"]["unexpected_calls"] if batch_016 else 0),
        "total_duplicate_successful_calls": batch_015["reconciliation"]["duplicate_successful_calls"] + (batch_016["reconciliation"]["duplicate_successful_calls"] if batch_016 else 0),
        "continuation_gate_result": gate,
        "batch_015_decision": batch_015["decision"]["execution_status"],
        "batch_016_decision": batch_016["decision"]["execution_status"] if batch_016 else "ATTENTION_BATCH_016_NOT_EXECUTED",
        "cumulative_validated_attention_calls": 168 + total_valid,
        "remaining_attention_calls": 204 - (168 + total_valid),
        **total_failures,
    }
    write_json(run_dir / "move_reconciliation.json", move_reconciliation)
    write_json(run_dir / "move_summary.json", move_reconciliation)
    move_decision = {"move_status": move_status, "scaling_decision": scaling}
    write_json(run_dir / "move_decision.json", move_decision)

    return {
        "run_dir": run_dir,
        "batch_015": batch_015,
        "batch_016": batch_016,
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
