#!/usr/bin/env python3
"""Execute frozen historical forecast Batch 003 with repaired transport controls."""
from __future__ import annotations

import argparse
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
COMPLETED_BATCH_001_ID = "PPHB-R1-FORECAST-EXECUTION-BATCH-001-20260729T125433Z-aed8c6eb2bf8"
COMPLETED_BATCH_002_ID = "PPHB-R1-FORECAST-PROVIDER-ERROR-REPLACEMENT-BATCH-002-2026-07-29T16:16:00Z-1e0d63b7c4c5"
EXPECTED_START_HEAD = "8f6b466c3e2a5f876cb4f086765e4b01dccdc93f"
USER_BATCH_LABEL = "FORECAST_BATCH_003"
FROZEN_BATCH_ID = "FCB_PACK_A_003"


class ForecastBatch003Error(RuntimeError):
    """Batch 003 cannot proceed under the frozen execution contract."""


def read_json(path: Path) -> dict[str, Any]:
    return batch_exec.read_json(path)


def prior_batch_reconciliation(run_id: str) -> dict[str, Any]:
    run_dir = OUTPUT_ROOT / run_id
    for name in ("batch_002_final_reconciliation.json", "batch_reconciliation.json"):
        path = run_dir / name
        if path.exists():
            return read_json(path)
    raise ForecastBatch003Error(f"RECONCILIATION_MISSING:{run_id}")


def verify_closed_priors() -> dict[str, Any]:
    batch_001 = prior_batch_reconciliation(COMPLETED_BATCH_001_ID)
    batch_002 = prior_batch_reconciliation(COMPLETED_BATCH_002_ID)
    if batch_001.get("successful_valid_calls") != 12:
        raise ForecastBatch003Error("BATCH_001_NOT_CLOSED")
    if batch_002.get("authoritative_valid_results") != 12:
        raise ForecastBatch003Error("BATCH_002_NOT_CLOSED")
    if batch_002.get("missing_authoritative_results") != 0:
        raise ForecastBatch003Error("BATCH_002_UNRESOLVED_RESULTS_PRESENT")
    if batch_002.get("provider_authority_conflicts") != 0:
        raise ForecastBatch003Error("BATCH_002_PROVIDER_AUTHORITY_CONFLICTS_PRESENT")
    return {
        "batch_001_authoritative_valid_results": 12,
        "batch_002_authoritative_valid_results": 12,
        "cumulative_authoritative_valid_results_before_batch_003": 24,
    }


def verify_batch_003_preflight(output_root: Path = OUTPUT_ROOT) -> dict[str, Any]:
    bundle = batch_exec.verified_batch_bundle(
        user_batch_label=USER_BATCH_LABEL,
        frozen_batch_id=FROZEN_BATCH_ID,
    )
    call_ids = [row["call"]["forecast_call_id"] for row in bundle["bundles"]]
    validated_call_ids = batch_exec.load_validated_call_ids(output_root)
    existing = sorted(call_id for call_id in call_ids if call_id in validated_call_ids)
    if existing:
        raise ForecastBatch003Error("BATCH_003_EXISTING_AUTHORITATIVE_RESULTS:" + ",".join(existing))
    return {
        "bundle": bundle,
        "authorized_call_ids": call_ids,
        "preexisting_authoritative_results": existing,
    }


def execute_batch_003(
    *,
    output_root: Path = OUTPUT_ROOT,
    fixed_timestamp: str | None = None,
    enforce_head: bool = True,
    auth_preflight=batch_exec.verify_google_preflight,
    dispatch=batch_exec.default_dispatch,
    script_service_factory_override: tuple[object, str] | None = None,
) -> dict[str, Any]:
    prior_summary = verify_closed_priors()
    batch_preflight = verify_batch_003_preflight(output_root=output_root)
    result = batch_exec.execute_batch(
        output_root=output_root,
        fixed_timestamp=fixed_timestamp,
        enforce_head=enforce_head,
        user_batch_label=USER_BATCH_LABEL,
        frozen_batch_id=FROZEN_BATCH_ID,
        auth_preflight=auth_preflight,
        dispatch=dispatch,
        expected_start_head=EXPECTED_START_HEAD,
        script_service_factory_override=script_service_factory_override,
    )
    return {
        **result,
        "prior_summary": prior_summary,
        "batch_preflight": batch_preflight,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, default=OUTPUT_ROOT)
    parser.add_argument("--fixed-timestamp", default=None)
    parser.add_argument("--skip-head-check", action="store_true")
    args = parser.parse_args(argv)
    result = execute_batch_003(
        output_root=args.output_root,
        fixed_timestamp=args.fixed_timestamp,
        enforce_head=not args.skip_head_check,
    )
    print(json.dumps({"run_dir": str(result["run_dir"]), **result["decision"]}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
