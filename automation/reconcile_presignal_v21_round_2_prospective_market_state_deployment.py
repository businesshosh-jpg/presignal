#!/usr/bin/env python3
"""Classify the requested Pack E acquisition deployment without promoting history."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "outputs" / "presignal_v21_full_round_1_forecast_execution"
OUTPUT_DIR = BASE / "PPHB-R2-PROSPECTIVE-MARKET-STATE-DEPLOYMENT-RECONCILIATION-20260804T030000Z"
HISTORICAL_COMMIT = "e5a0ff288eb1f6fc228936cb1c693ed2bb2ab80f"
HISTORICAL_PATH = "automation/build_true_shared_market_state_pack_e_v0.py"


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def historical_source() -> str:
    return subprocess.check_output(["git", "show", f"{HISTORICAL_COMMIT}:{HISTORICAL_PATH}"], cwd=ROOT, text=True)


def reconcile(output_dir: Path = OUTPUT_DIR) -> dict[str, Any]:
    if output_dir.exists():
        raise RuntimeError("PROSPECTIVE_MARKET_STATE_DEPLOYMENT_RECONCILIATION_ALREADY_EXISTS")
    source = historical_source()
    expected = {
        "USDJPY_RETURN_1H_PRESESSION", "USDJPY_RETURN_4H_PRESESSION", "USDJPY_RETURN_24H_PRESESSION", "USDJPY_TREND_LABEL", "USDJPY_REALIZED_VOL_1H_PRESESSION", "NEXT_HIGH_IMPORTANCE_EVENT_WITHIN_24H", "NEXT_HIGH_IMPORTANCE_EVENT_WITHIN_48H", "NEXT_CPI_OR_FOMC_WITHIN_72H", "NEXT_NFP_WITHIN_7D", "EVENT_CLUSTER_DENSITY_NEXT_24H", "US2Y_YIELD_LEVEL", "US10Y_YIELD_LEVEL", "US2Y_CHANGE_FROM_PRIOR_CLOSE", "US10Y_CHANGE_FROM_PRIOR_CLOSE", "US10Y_MINUS_US2Y_CURVE", "DXY_LEVEL", "DXY_CHANGE_PRESESSION", "DXY_DIRECTION_LABEL",
    }
    if not all(field in source for field in expected):
        raise RuntimeError("HISTORICAL_FIELD_UNIVERSE_SOURCE_CONFLICT")
    api = (ROOT / "apps_script" / "automation_api.js").read_text()
    evidence = {
        "reconciliation_id": output_dir.name,
        "decisions": {
            "field_contract": "ROUND_2_SHARED_MARKET_STATE_FIELD_CONTRACT_BLOCKED",
            "source_authority": "ROUND_2_SHARED_MARKET_STATE_SOURCE_AUTHORITY_CONFLICT",
            "contract": "ROUND_2_SHARED_MARKET_STATE_CONTRACT_BLOCKED",
            "adapter": "ROUND_2_PROSPECTIVE_SHARED_MARKET_STATE_ADAPTER_BLOCKED",
            "lead_time": "ROUND_2_SHARED_MARKET_STATE_LEAD_TIME_BLOCKED",
            "controller": "CONTINUOUS_ROUND_2_PRE_CUTOFF_ORCHESTRATION_BLOCKED",
            "new_slice": "ROUND_2_NEW_SLICE_GOVERNANCE_BLOCKED",
        },
        "historical_evidence": {
            "source_commit": HISTORICAL_COMMIT,
            "source_path": HISTORICAL_PATH,
            "source_fingerprint": digest(source),
            "base_field_universe": sorted(expected),
            "proxy_fields_explicitly_excluded": ["USD_INDEX_PROXY_LEVEL", "USD_INDEX_PROXY_CHANGE"],
            "request_dependent_capabilities": ["EVENT_CONSENSUS_PRIOR_DETAIL", "INFLATION_NARRATIVE_SOURCE_GROUNDED", "TREASURY_2Y_10Y_PRESESSION_STATE", "DXY_PRESESSION_STATE", "USDJPY_PRESESSION_STATE", "UPCOMING_EVENT_CALENDAR"],
            "non_acquirable_or_ungoverned_capabilities": ["EQUITY_PRESESSION_TONE", "USDJPY_OPTION_IMPLIED_VOLATILITY", "LABOR_MARKET_CONTEXT", "GROWTH_CONTEXT", "USDJPY_CROSS_ASSET_CORRELATION", "HISTORICAL_EVENT_SENSITIVITY"],
            "historical_dependencies": ["Market_State_Pack_Shadow", "Market_Session_Members", "Market_State_Pack_Candidates", "Market_State_Pack_Acquisition_Backlog", "historical request-fulfillment audit", "source bundles"],
        },
        "prospective_source_status": {
            "return_only_adapter_present": "function apiBuildSharedMarketStatePack" in api,
            "current_deployed_equivalent": "NONE",
            "reason": "The historical universe is not a fixed prospective field contract: values and capabilities depend on mutable historical sheets, request wording, source bundles, and explicitly unimplemented categories. No accepted source precedence, response schema, timestamp rule, or exact ceiling maps every admissible field to one live route.",
        },
        "deployment": {"attempted": False, "reason": "Deployment would encode an ungoverned field/source selection and change Pack E semantics.", "google_writes": 0, "provider_calls": 0, "market_data_calls": 0, "retries": 0},
        "snapshot_application": {"performed": False, "reason": "No admission deadline can be calculated before every source route has a bounded completion time."},
        "required_next_authority": "Freeze a scientific prospective Pack E specification that selects a closed field subset, a single exact live source/schema for each field, and explicit unavailable treatment before implementing or deploying an acquisition adapter.",
        "recorded_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
    }
    evidence["fingerprint"] = digest({key: value for key, value in evidence.items() if key not in {"recorded_utc", "fingerprint"}})
    output_dir.mkdir(parents=True)
    (output_dir / "prospective_market_state_deployment_reconciliation.json").write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n")
    return evidence


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR); args = parser.parse_args()
    print(json.dumps(reconcile(args.output_dir), sort_keys=True)); return 0


if __name__ == "__main__":
    raise SystemExit(main())
