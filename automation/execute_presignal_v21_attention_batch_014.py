#!/usr/bin/env python3
"""Execute or fail-closed ATTN_BATCH_014 from the frozen Attention execution plan."""
from __future__ import annotations

import argparse
import json
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Mapping

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from automation import execute_presignal_v21_attention_batch_004 as batch004

PLAN_ID = batch004.PLAN_ID
PLAN_ROOT = batch004.PLAN_ROOT
OUTPUT_ROOT = batch004.OUTPUT_ROOT
BATCH_ID = "ATTN_BATCH_014"
EXPECTED_CALL_COUNT = 12
EXPECTED_START_HEAD = "7246c2ebd82892572798f67f390ccaa7e2124adc"
TOKEN_PATH = batch004.TOKEN_PATH
GOVERNING_BATCH_001_CLOSURE_ID = batch004.GOVERNING_BATCH_001_CLOSURE_ID
GOVERNING_BATCH_002_CLOSURE_ID = batch004.GOVERNING_BATCH_002_CLOSURE_ID
GOVERNING_BATCH_003_CLOSURE_ID = "PPHB-R1-ATTENTION-BATCH-003-COMPLETENESS-RETRY-20260729T053347Z-3bbe67af1930"
GOVERNING_BATCH_004_EXECUTION_ID = "PPHB-R1-ATTENTION-EXECUTION-BATCH-004-20260729T060007Z-2b28132d61f4"
GOVERNING_BATCH_005_EXECUTION_ID = "PPHB-R1-ATTENTION-EXECUTION-BATCH-005-20260729T062307Z-a8d4e499fc50"
GOVERNING_BATCH_006_EXECUTION_ID = "PPHB-R1-ATTENTION-EXECUTION-BATCH-006-20260729T063514Z-a9329b56342b"
GOVERNING_BATCH_007_EXECUTION_ID = "PPHB-R1-ATTENTION-EXECUTION-BATCH-007-20260729T065113Z-dfd5c326249f"
GOVERNING_BATCH_008_EXECUTION_ID = "PPHB-R1-ATTENTION-EXECUTION-BATCH-008-20260729T070157Z-9a7f35ddf62d"
GOVERNING_BATCH_009_EXECUTION_ID = "PPHB-R1-ATTENTION-EXECUTION-BATCH-009-20260729T071942Z-6f918ad51b93"
GOVERNING_BATCH_010_EXECUTION_ID = "PPHB-R1-ATTENTION-EXECUTION-BATCH-010-20260729T072954Z-a6226ec669a9"
GOVERNING_BATCHES_011_012_COORDINATION_ID = "PPHB-R1-ATTENTION-EXECUTION-BATCHES-011-012-20260729T081001Z-ec325133cb49"
GOVERNING_BATCH_011_EXECUTION_ID = "PPHB-R1-ATTENTION-EXECUTION-BATCH-011-20260729T081001Z-a52246208ecd"
GOVERNING_BATCH_012_EXECUTION_ID = "PPHB-R1-ATTENTION-EXECUTION-BATCH-012-20260729T081445Z-6b95a2de5cac"


def load_batch_calls() -> list[dict[str, Any]]:
    calls = batch004.base.load_batch_calls(BATCH_ID)
    if len(calls) != EXPECTED_CALL_COUNT:
        raise batch004.base.AttentionBatchError("BATCH_014_CALL_COUNT_MISMATCH")
    prior_ids: set[str] = set()
    for prior_batch_id in (
        "ATTN_BATCH_001",
        "ATTN_BATCH_002",
        "ATTN_BATCH_003",
        "ATTN_BATCH_004",
        "ATTN_BATCH_005",
        "ATTN_BATCH_006",
        "ATTN_BATCH_007",
        "ATTN_BATCH_008",
        "ATTN_BATCH_009",
        "ATTN_BATCH_010",
        "ATTN_BATCH_011",
        "ATTN_BATCH_012",
        "ATTN_BATCH_013",
    ):
        prior_ids.update(row["call_id"] for row in batch004.base.load_batch_calls(prior_batch_id))
    overlap = [row["call_id"] for row in calls if row["call_id"] in prior_ids]
    if overlap:
        raise batch004.base.AttentionBatchError("BATCH_014_OVERLAPS_PRIOR_BATCH:" + ",".join(overlap))
    return calls


@contextmanager
def patched_batch004() -> Any:
    original = {
        "BATCH_ID": batch004.BATCH_ID,
        "EXPECTED_CALL_COUNT": batch004.EXPECTED_CALL_COUNT,
        "EXPECTED_START_HEAD": batch004.EXPECTED_START_HEAD,
        "GOVERNING_BATCH_003_CLOSURE_ID": batch004.GOVERNING_BATCH_003_CLOSURE_ID,
        "PRIOR_BATCH_IDS": batch004.PRIOR_BATCH_IDS,
        "RUN_ID_PREFIX": batch004.RUN_ID_PREFIX,
        "EXECUTION_STATUS_COMPLETE": batch004.EXECUTION_STATUS_COMPLETE,
        "EXECUTION_STATUS_PARTIAL": batch004.EXECUTION_STATUS_PARTIAL,
        "EXECUTION_STATUS_BLOCKED": batch004.EXECUTION_STATUS_BLOCKED,
        "SCALING_READY": batch004.SCALING_READY,
        "SCALING_REPAIR": batch004.SCALING_REPAIR,
        "SCALING_RETRY": batch004.SCALING_RETRY,
        "FAILED_CALL_RETRY_RECOMMENDATION": batch004.FAILED_CALL_RETRY_RECOMMENDATION,
    }
    batch004.BATCH_ID = BATCH_ID
    batch004.EXPECTED_CALL_COUNT = EXPECTED_CALL_COUNT
    batch004.EXPECTED_START_HEAD = EXPECTED_START_HEAD
    batch004.GOVERNING_BATCH_003_CLOSURE_ID = GOVERNING_BATCH_003_CLOSURE_ID
    batch004.PRIOR_BATCH_IDS = (
        "ATTN_BATCH_001",
        "ATTN_BATCH_002",
        "ATTN_BATCH_003",
        "ATTN_BATCH_004",
        "ATTN_BATCH_005",
        "ATTN_BATCH_006",
        "ATTN_BATCH_007",
        "ATTN_BATCH_008",
        "ATTN_BATCH_009",
        "ATTN_BATCH_010",
        "ATTN_BATCH_011",
        "ATTN_BATCH_012",
        "ATTN_BATCH_013",
    )
    batch004.RUN_ID_PREFIX = "PPHB-R1-ATTENTION-EXECUTION-BATCH-014-"
    batch004.EXECUTION_STATUS_COMPLETE = "ATTENTION_BATCH_014_COMPLETE"
    batch004.EXECUTION_STATUS_PARTIAL = "ATTENTION_BATCH_014_PARTIALLY_COMPLETE"
    batch004.EXECUTION_STATUS_BLOCKED = "ATTENTION_BATCH_014_BLOCKED"
    batch004.SCALING_READY = "READY_FOR_ATTENTION_BATCH_015"
    batch004.SCALING_REPAIR = "REPAIR_BEFORE_BATCH_015"
    batch004.SCALING_RETRY = "RETRY_FAILED_BATCH_014_CALLS_REQUIRES_AUTHORIZATION"
    batch004.FAILED_CALL_RETRY_RECOMMENDATION = "NO_AUTOMATIC_RETRY_IN_BATCH_014"
    try:
        yield
    finally:
        for key, value in original.items():
            setattr(batch004, key, value)


def patch_run_metadata(run_dir: Path) -> None:
    for path in (
        run_dir / "run_manifest.json",
        run_dir / "batch_execution_contract.json",
        run_dir / "governing_artifact_manifest.json",
    ):
        if not path.exists():
            continue
        data = batch004.read_json(path)
        data["governing_batch_004_execution_id"] = GOVERNING_BATCH_004_EXECUTION_ID
        data["governing_batch_005_execution_id"] = GOVERNING_BATCH_005_EXECUTION_ID
        data["governing_batch_006_execution_id"] = GOVERNING_BATCH_006_EXECUTION_ID
        data["governing_batch_007_execution_id"] = GOVERNING_BATCH_007_EXECUTION_ID
        data["governing_batch_008_execution_id"] = GOVERNING_BATCH_008_EXECUTION_ID
        data["governing_batch_009_execution_id"] = GOVERNING_BATCH_009_EXECUTION_ID
        data["governing_batch_010_execution_id"] = GOVERNING_BATCH_010_EXECUTION_ID
        data["governing_batches_011_012_coordination_id"] = GOVERNING_BATCHES_011_012_COORDINATION_ID
        data["governing_batch_011_execution_id"] = GOVERNING_BATCH_011_EXECUTION_ID
        data["governing_batch_012_execution_id"] = GOVERNING_BATCH_012_EXECUTION_ID
        batch004.write_json(path, data)


def execute_batch(
    *,
    output_root: Path = OUTPUT_ROOT,
    dispatcher: Callable[[Mapping[str, Any]], Mapping[str, Any]] | None = None,
    fixed_timestamp: str | None = None,
    resume_run_dir: Path | None = None,
    source_session_loader: Callable[[], tuple[dict[str, Any], dict[str, list[dict[str, Any]]]]] | None = None,
    enforce_head: bool = True,
) -> dict[str, Any]:
    with patched_batch004():
        result = batch004.execute_batch(
            output_root=output_root,
            dispatcher=dispatcher,
            fixed_timestamp=fixed_timestamp,
            resume_run_dir=resume_run_dir,
            source_session_loader=source_session_loader,
            enforce_head=enforce_head,
        )
    patch_run_metadata(result["run_dir"])
    return result


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
                "skipped_already_successful_calls": result["reconciliation"]["skipped_already_successful_calls"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
