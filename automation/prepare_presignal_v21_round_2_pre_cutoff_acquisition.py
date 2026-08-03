#!/usr/bin/env python3
"""Record the local Round 2 prerequisite-route decision without external access."""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "outputs" / "presignal_v21_full_round_1_forecast_execution"
OUTPUT_DIR = BASE / "PPHB-R2-PRE-CUTOFF-PACK-ACQUISITION-PREPARATION-20260804T024000Z"


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def prepare(output_dir: Path = OUTPUT_DIR) -> dict[str, Any]:
    if output_dir.exists():
        raise RuntimeError("PRE_CUTOFF_PREPARATION_ALREADY_EXISTS")
    route = {
        "decision": "ROUND_2_PRE_CUTOFF_PACK_ACQUISITION_ROUTE_CONFLICT",
        "slice_001_disposition": "ROUND_2_SLICE_001_PRE_CUTOFF_PACK_INPUTS_MISSING_NON_REUSABLE",
        "canonical_stages": [
            "automation/build_presignal_v21_episodes.py::build_population",
            "automation/presignal_v21_minimal_prospective_lineage_v1.py::build_prospective_attention",
            "automation/presignal_v21_minimal_prospective_lineage_v1.py::build_prospective_requests",
            "automation/presignal_v21_minimal_prospective_lineage_v1.py::build_prospective_packs",
            "automation/build_presignal_v21_event_path_inputs.py::build_episode_inputs",
        ],
        "ordering": ["authoritative_future_event", "episode_admission", "attention", "information_requests", "shared_market_state", "pack_a_and_pack_e_materialization", "forecast_call_freeze", "t_minus_15_dispatch"],
        "confirmed_requirements": {"pack_a": ["parsed_pre_cutoff_attention", "parsed_pre_cutoff_information_requests"], "pack_e": ["pack_a_requirements", "timestamped_pre_cutoff_shared_market_state_items"]},
        "unresolved_authority": "The canonical Pack builder validates supplied shared_market_state_items but the accepted prospective implementation has no authoritative acquisition source or ceiling for those items. Its only orchestrated source is a historical replay package, which cannot be promoted into prospective evidence.",
        "lead_time": {"known_provider_stage_limits_seconds": {"attention": 180, "information_requests": 180}, "unknown_required_component": "shared-market-state acquisition source and its bounded execution limit", "decision": "ADMISSION_DEADLINE_NOT_DERIVABLE_WITHOUT_UNGOVERNED_SOURCE_LIMIT"},
        "external_activity": {"provider_calls": 0, "google_writes": 0, "market_data_calls": 0, "outcome_activity": 0, "evaluation_activity": 0, "retries": 0},
    }
    controller = {"decision": "CONTINUOUS_ROUND_2_PRE_CUTOFF_ORCHESTRATION_BLOCKED", "correction": "Controller now refuses forecast-call freezing until both immutable Pack-input artifact IDs and fingerprints exist.", "state": "PREREQUISITE_GOVERNANCE_BLOCKED", "new_slice_decision": "ROUND_2_NEW_SLICE_GOVERNANCE_BLOCKED", "envelope": "NOT_FROZEN: source authority and lead-time ceiling are unresolved.", "forecast_dispatch_authorization": "NOT_PREPARED"}
    evidence = {"preparation_id": output_dir.name, "route": route, "controller": controller, "recorded_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")}
    evidence["fingerprint"] = digest({key: value for key, value in evidence.items() if key not in {"recorded_utc", "fingerprint"}})
    output_dir.mkdir(parents=True)
    (output_dir / "pre_cutoff_acquisition_route_reconciliation.json").write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n")
    return evidence


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR); args = parser.parse_args()
    print(json.dumps(prepare(args.output_dir), sort_keys=True)); return 0


if __name__ == "__main__":
    raise SystemExit(main())
