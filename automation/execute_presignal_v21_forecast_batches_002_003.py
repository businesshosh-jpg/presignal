#!/usr/bin/env python3
"""Execute frozen historical forecast batches 002 and 003 sequentially."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from automation import execute_presignal_v21_forecast_batch_001 as batch_exec

OUTPUT_ROOT = batch_exec.OUTPUT_ROOT
PLAN_ID = batch_exec.PLAN_ID
PRIOR_BATCH_001_ID = "PPHB-R1-FORECAST-EXECUTION-BATCH-001-20260729T125433Z-aed8c6eb2bf8"
EXPECTED_START_HEAD = "0ed63ddcd918cb2e28f07b1f429a3dbaa1aba1b5"
BATCH_002 = ("FORECAST_BATCH_002", "FCB_PACK_A_002")
BATCH_003 = ("FORECAST_BATCH_003", "FCB_PACK_A_003")


class ForecastCoordinatorError(RuntimeError):
    """Sequential forecast batch coordination failed closed."""


def canonical_json(value: Any) -> str:
    return batch_exec.canonical_json(value)


def now() -> str:
    return batch_exec.now()


def write_json(path: Path, value: Any) -> None:
    batch_exec.write_json(path, value)


def materialize_run(output_root: Path, fixed_timestamp: str | None = None) -> Path:
    timestamp = fixed_timestamp or now()
    seed = {"plan_id": PLAN_ID, "move": "FORECAST_BATCHES_002_003", "timestamp": timestamp}
    run_id = (
        "PPHB-R1-FORECAST-EXECUTION-BATCHES-002-003-"
        + timestamp.replace(":", "").replace("-", "")
        + "-"
        + hashlib.sha256(canonical_json(seed).encode("utf-8")).hexdigest()[:12]
    )
    return output_root / run_id


def validate_authorized_batches() -> list[dict[str, Any]]:
    rows = batch_exec.read_jsonl(batch_exec.PLAN_ROOT / "forecast_batch_manifest.jsonl")
    next_two = rows[1:3]
    if [row["batch_id"] for row in next_two] != [BATCH_002[1], BATCH_003[1]]:
        raise ForecastCoordinatorError("NEXT_BATCH_IDENTITIES_MISMATCH")
    bundles = [
        batch_exec.verified_batch_bundle(user_batch_label=BATCH_002[0], frozen_batch_id=BATCH_002[1]),
        batch_exec.verified_batch_bundle(user_batch_label=BATCH_003[0], frozen_batch_id=BATCH_003[1]),
    ]
    batch_001_ids = {
        row["call"]["forecast_call_id"]
        for row in batch_exec.verified_batch_bundle().get("bundles", [])
    }
    batch_002_ids = {row["call"]["forecast_call_id"] for row in bundles[0]["bundles"]}
    batch_003_ids = {row["call"]["forecast_call_id"] for row in bundles[1]["bundles"]}
    if batch_001_ids & batch_002_ids:
        raise ForecastCoordinatorError("BATCH_002_OVERLAPS_BATCH_001")
    if batch_001_ids & batch_003_ids:
        raise ForecastCoordinatorError("BATCH_003_OVERLAPS_BATCH_001")
    if batch_002_ids & batch_003_ids:
        raise ForecastCoordinatorError("BATCH_002_003_OVERLAP")
    return bundles


def initialize_run(run_dir: Path, bundles: list[Mapping[str, Any]]) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    write_json(
        run_dir / "run_manifest.json",
        {
            "move": "FORECAST_BATCHES_002_003",
            "plan_id": PLAN_ID,
            "prior_batch_001_id": PRIOR_BATCH_001_ID,
            "authorized_batches": [BATCH_002[1], BATCH_003[1]],
            "authorized_calls": 24,
            "maximum_provider_calls": 24,
        },
    )
    write_json(
        run_dir / "governing_artifact_manifest.json",
        {
            "forecast_plan_id": PLAN_ID,
            "prior_batch_001_id": PRIOR_BATCH_001_ID,
            "pack_construction_id": batch_exec.PACK_CONSTRUCTION_ID,
            "authorized_batch_ids": [BATCH_002[1], BATCH_003[1]],
        },
    )
    write_json(
        run_dir / "authorized_batch_manifest.json",
        {
            "batches": [
                {
                    "user_batch_label": bundle["user_batch_label"],
                    "frozen_batch_id": bundle["frozen_batch_id"],
                    "pack_type": bundle["pack_type"],
                    "authorized_call_ids": [row["call"]["forecast_call_id"] for row in bundle["bundles"]],
                }
                for bundle in bundles
            ]
        },
    )


def continuation_decision(batch_002_result: Mapping[str, Any]) -> tuple[str, dict[str, Any]]:
    reconciliation = batch_002_result["reconciliation"]
    decision = batch_002_result["decision"]
    shared_failure = any(
        (
            reconciliation["unexpected_calls"],
            reconciliation["duplicate_successful_calls"],
            reconciliation["manifest_transport_conflicts"],
            reconciliation["failed_provider_authority_calls"],
            reconciliation["failed_parse_calls"],
            reconciliation["failed_validation_calls"],
        )
    )
    if batch_002_result["auth_result"]["read_only_preflight_result"] != "PASSED":
        return "STOP_BEFORE_FORECAST_BATCH_003_GOVERNANCE_FAILURE", {
            "reason": "AUTHENTICATION_OR_RESOURCE_IDENTITY_FAILURE",
            "batch_002_decision": decision,
        }
    if shared_failure:
        return "STOP_BEFORE_FORECAST_BATCH_003_SHARED_FAILURE", {
            "reason": "BATCH_002_SHARED_CONTROL_FAILURE",
            "batch_002_decision": decision,
            "reconciliation": reconciliation,
        }
    return "PROCEED_TO_FORECAST_BATCH_003", {
        "reason": "BATCH_002_CONTROLS_REMAIN_SOUND",
        "batch_002_decision": decision,
        "reconciliation": reconciliation,
    }


def execute_move(
    *,
    output_root: Path = OUTPUT_ROOT,
    fixed_timestamp: str | None = None,
    enforce_head: bool = True,
    auth_preflight=batch_exec.verify_google_preflight,
    dispatch=batch_exec.default_dispatch,
) -> dict[str, Any]:
    if batch_exec.git_branch() != "codex/immediate-impulse-outcome-recovery-r1":
        raise ForecastCoordinatorError("BRANCH_MISMATCH")
    head = batch_exec.git_head()
    if enforce_head and head != EXPECTED_START_HEAD and not batch_exec.is_descendant_of(EXPECTED_START_HEAD):
        raise ForecastCoordinatorError("HEAD_ANCESTRY_NOT_CLEAN")
    bundles = validate_authorized_batches()
    run_dir = materialize_run(output_root=output_root, fixed_timestamp=fixed_timestamp)
    initialize_run(run_dir, bundles)

    try:
        batch_002_result = batch_exec.execute_batch(
            output_root=output_root,
            fixed_timestamp=fixed_timestamp,
            enforce_head=enforce_head,
            user_batch_label=BATCH_002[0],
            frozen_batch_id=BATCH_002[1],
            auth_preflight=auth_preflight,
            dispatch=dispatch,
        )
    except Exception as exc:
        write_json(run_dir / "batch_002_result_reference.json", {"executed": False, "reason": type(exc).__name__, "error": str(exc)})
        write_json(
            run_dir / "continuation_gate_decision.json",
            {
                "continuation_gate_decision": "STOP_BEFORE_FORECAST_BATCH_003_GOVERNANCE_FAILURE",
                "evidence": {"reason": "BATCH_002_PRE_DISPATCH_AUTH_OR_GOVERNANCE_FAILURE", "error": str(exc), "exception_type": type(exc).__name__},
            },
        )
        write_json(run_dir / "batch_003_result_reference.json", {"executed": False, "reason": "BATCH_002_NOT_COMPLETED"})
        move_reconciliation = {
            "authorized_batches": 2,
            "executed_batches": 0,
            "total_authorized_calls": 24,
            "total_attempted_calls": 0,
            "total_valid_calls": 0,
            "failed_transport_calls": 0,
            "failed_provider_calls": 0,
            "failed_provider_authority_calls": 0,
            "failed_parse_calls": 0,
            "failed_validation_calls": 0,
            "total_skipped_calls": 0,
            "total_unexpected_calls": 0,
            "total_duplicate_successful_calls": 0,
            "continuation_gate_result": "STOP_BEFORE_FORECAST_BATCH_003_GOVERNANCE_FAILURE",
            "cumulative_validated_forecast_calls": 12,
            "remaining_planned_forecast_calls": 552,
        }
        write_json(run_dir / "move_reconciliation.json", move_reconciliation)
        write_json(run_dir / "move_summary.json", move_reconciliation)
        write_json(
            run_dir / "move_decision.json",
            {
                "move_status": "FORECAST_BATCHES_002_003_BLOCKED",
                "scaling_decision": "REPAIR_BEFORE_FURTHER_FORECAST_EXECUTION",
                "batch_002_status": "FORECAST_BATCH_002_BLOCKED",
                "batch_003_status": "FORECAST_BATCH_003_NOT_EXECUTED",
            },
        )
        return {
            "run_dir": run_dir,
            "batch_002": None,
            "batch_003": None,
            "continuation_gate": "STOP_BEFORE_FORECAST_BATCH_003_GOVERNANCE_FAILURE",
            "continuation_evidence": {"reason": "BATCH_002_PRE_DISPATCH_AUTH_OR_GOVERNANCE_FAILURE", "error": str(exc), "exception_type": type(exc).__name__},
            "move_reconciliation": move_reconciliation,
            "move_decision": {"move_status": "FORECAST_BATCHES_002_003_BLOCKED", "scaling_decision": "REPAIR_BEFORE_FURTHER_FORECAST_EXECUTION"},
            "blocked_exception": {"type": type(exc).__name__, "message": str(exc)},
        }
    write_json(
        run_dir / "batch_002_result_reference.json",
        {
            "run_dir": str(batch_002_result["run_dir"]),
            "decision": batch_002_result["decision"],
            "reconciliation": batch_002_result["reconciliation"],
        },
    )
    gate, evidence = continuation_decision(batch_002_result)
    write_json(run_dir / "continuation_gate_decision.json", {"continuation_gate_decision": gate, "evidence": evidence})

    batch_003_result: dict[str, Any] | None = None
    if gate == "PROCEED_TO_FORECAST_BATCH_003":
        batch_003_result = batch_exec.execute_batch(
            output_root=output_root,
            fixed_timestamp=fixed_timestamp,
            enforce_head=enforce_head,
            user_batch_label=BATCH_003[0],
            frozen_batch_id=BATCH_003[1],
            auth_preflight=auth_preflight,
            dispatch=dispatch,
        )
        write_json(
            run_dir / "batch_003_result_reference.json",
            {
                "run_dir": str(batch_003_result["run_dir"]),
                "decision": batch_003_result["decision"],
                "reconciliation": batch_003_result["reconciliation"],
            },
        )
    else:
        write_json(run_dir / "batch_003_result_reference.json", {"executed": False, "reason": gate})

    batches = [batch_002_result] + ([batch_003_result] if batch_003_result else [])
    total_failures = {
        "failed_transport_calls": sum(item["reconciliation"]["failed_transport_calls"] for item in batches if item),
        "failed_provider_calls": sum(item["reconciliation"]["failed_provider_calls"] for item in batches if item),
        "failed_provider_authority_calls": sum(item["reconciliation"]["failed_provider_authority_calls"] for item in batches if item),
        "failed_parse_calls": sum(item["reconciliation"]["failed_parse_calls"] for item in batches if item),
        "failed_validation_calls": sum(item["reconciliation"]["failed_validation_calls"] for item in batches if item),
    }
    total_valid = sum(item["reconciliation"]["successful_valid_calls"] for item in batches if item)
    total_attempted = sum(item["reconciliation"]["attempted_provider_calls"] for item in batches if item)
    total_skipped = sum(item["reconciliation"]["skipped_already_successful_calls"] for item in batches if item)
    total_unexpected = sum(item["reconciliation"]["unexpected_calls"] for item in batches if item)
    total_duplicates = sum(item["reconciliation"]["duplicate_successful_calls"] for item in batches if item)
    move_reconciliation = {
        "authorized_batches": 2,
        "executed_batches": len(batches),
        "total_authorized_calls": 24,
        "total_attempted_calls": total_attempted,
        "total_valid_calls": total_valid,
        **total_failures,
        "total_skipped_calls": total_skipped,
        "total_unexpected_calls": total_unexpected,
        "total_duplicate_successful_calls": total_duplicates,
        "continuation_gate_result": gate,
        "cumulative_validated_forecast_calls": 12 + total_valid,
        "remaining_planned_forecast_calls": 564 - (12 + total_valid),
    }
    write_json(run_dir / "move_reconciliation.json", move_reconciliation)
    write_json(run_dir / "move_summary.json", move_reconciliation)

    if gate != "PROCEED_TO_FORECAST_BATCH_003":
        move_status = "FORECAST_BATCHES_002_003_STOPPED_AFTER_BATCH_002"
        scaling_decision = "REPAIR_BEFORE_FURTHER_FORECAST_EXECUTION"
        batch_003_status = "FORECAST_BATCH_003_NOT_EXECUTED"
    elif any(total_failures.values()):
        move_status = "FORECAST_BATCHES_002_003_PARTIALLY_COMPLETE"
        scaling_decision = "RETRY_FAILED_CALLS_REQUIRES_AUTHORIZATION"
        batch_003_status = batch_003_result["decision"]["batch_status"]
    else:
        move_status = "FORECAST_BATCHES_002_003_COMPLETE"
        scaling_decision = "READY_FOR_NEXT_FORECAST_BATCH_RANGE"
        batch_003_status = batch_003_result["decision"]["batch_status"]
    write_json(
        run_dir / "move_decision.json",
        {
            "move_status": move_status,
            "scaling_decision": scaling_decision,
            "batch_002_status": batch_002_result["decision"]["batch_status"],
            "batch_003_status": batch_003_status,
        },
    )
    return {
        "run_dir": run_dir,
        "batch_002": batch_002_result,
        "batch_003": batch_003_result,
        "continuation_gate": gate,
        "continuation_evidence": evidence,
        "move_reconciliation": move_reconciliation,
        "move_decision": {"move_status": move_status, "scaling_decision": scaling_decision},
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, default=OUTPUT_ROOT)
    parser.add_argument("--fixed-timestamp", default=None)
    parser.add_argument("--skip-head-check", action="store_true")
    args = parser.parse_args(argv)
    result = execute_move(
        output_root=args.output_root,
        fixed_timestamp=args.fixed_timestamp,
        enforce_head=not args.skip_head_check,
    )
    print(json.dumps({"run_dir": str(result["run_dir"]), **result["move_decision"]}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
