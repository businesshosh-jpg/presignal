#!/usr/bin/env python3
"""Recover one frozen Pack A result from preserved raw output only."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from automation import run_presignal_v21_single_event_path_pair_v1_1 as step6
from automation.build_presignal_v21_event_path_inputs import reject_leakage

OUTPUT_ROOT = ROOT / "outputs" / "presignal_v21_full_round_1_forecast_execution"
RUN_ID = "PPHB-R1-PACK-A-DETERMINISTIC-RAW-RECOVERY-20260803T080000Z-9f2e4c7a1d66"
TARGET = "FCL_3d10ae8285471f4e3a980b79"
SOURCE_RUN = OUTPUT_ROOT / "PPHB-R1-FORECAST-EXECUTION-BATCH-010-20260801T190644Z-17f70b192668"
FEASIBILITY_RUN = OUTPUT_ROOT / "PPHB-R1-PACK-A-TERMINAL-INVALID-RECOVERY-FEASIBILITY-REVIEW-20260803T070000Z-385b501cd5dc"
FULL_RUN = OUTPUT_ROOT / "PPHB-R1-FORECAST-FULL-EXECUTION-COMPLETION-20260803T060000Z"


def read_row(path: Path, key: str, value: str) -> dict[str, Any]:
    for line in path.read_text().splitlines():
        row = json.loads(line)
        if row.get(key) == value:
            return row
    raise RuntimeError(f"missing {value} in {path}")


def digest(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def raw_digest(raw: str) -> str:
    return "sha256:" + hashlib.sha256(raw.encode()).hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True) + "\n")


def main() -> None:
    manifest = read_row(SOURCE_RUN / "batch_call_manifest.jsonl", "forecast_call_id", TARGET)
    transport = read_row(SOURCE_RUN / "raw_transport_results.jsonl", "forecast_call_id", TARGET)
    raw_row = read_row(SOURCE_RUN / "raw_provider_outputs.jsonl", "forecast_call_id", TARGET)
    authority = read_row(SOURCE_RUN / "provider_authority_results.jsonl", "forecast_call_id", TARGET)
    parse_row = read_row(SOURCE_RUN / "forecast_parse_results.jsonl", "forecast_call_id", TARGET)
    failure = read_row(SOURCE_RUN / "failed_call_ledger.jsonl", "forecast_call_id", TARGET)
    operation = read_row(SOURCE_RUN / "operation_journal.jsonl", "forecast_call_id", TARGET)
    raw = raw_row["raw_provider_output"]
    repaired, transformation = step6.repair_missing_path_boundary(raw)
    if transformation.get("status") != "REPAIRED_ONE_STRUCTURAL_BOUNDARY":
        raise RuntimeError("recovery did not find exactly one structural boundary")
    normalized, parse_audit = step6.normalize_provider_output(raw)
    # Reparse the repaired representation explicitly for the append-only recovery record.
    reparsed, repaired_audit = step6.normalize_provider_output(repaired)
    if normalized != reparsed:
        raise RuntimeError("repaired normalization changed semantic values")
    if authority.get("authority_passed") is not True:
        raise RuntimeError("original provider authority did not pass")
    if manifest.get("provider") != authority.get("actual_provider") or manifest.get("model") != authority.get("actual_model"):
        raise RuntimeError("provider authority mismatch")
    reject_leakage(reparsed)
    episode = manifest["prompt_payload"]["episode"]
    bridge = transport["raw_transport_result"]
    input_row = {
        "information_arm": "PACK_A",
        "episode_id": manifest["episode_id"],
        "source_session_id": operation["source_session_id"],
        "provider": manifest["provider"],
        "model": manifest["model"],
        "forecast_cutoff_ts": manifest["historical_cutoff"],
        "episode_members": episode["members"],
    }
    prediction, paths = step6.response_to_contract(
        reparsed,
        input_row,
        run_id=RUN_ID,
        created_ts=bridge["completed_timestamp"],
        raw_output=repaired,
        bridge_result=bridge,
    )
    reject_leakage(prediction)
    reject_leakage(paths)
    out = OUTPUT_ROOT / RUN_ID
    write_json(out / "run_manifest.json", {
        "run_id": RUN_ID,
        "move_type": "NO_PROVIDER_CALL_DETERMINISTIC_STRUCTURAL_RECOVERY",
        "target_forecast_call_id": TARGET,
        "source_execution_run": SOURCE_RUN.name,
        "feasibility_run": FEASIBILITY_RUN.name,
        "provider_calls": 0,
        "google_access": False,
        "outcome_access": False,
        "market_data_access": False,
        "evaluation": False,
        "recovery_is_not_retry": True,
    })
    write_json(out / "recovery_transformation.json", {
        "forecast_call_id": TARGET,
        "original_terminal_decision": failure,
        "original_raw_output_hash": raw_digest(raw),
        "repaired_raw_representation_hash": raw_digest(repaired),
        "recovery_rule_version": "PACK_A_PATH_BOUNDARY_REPAIR_V1",
        "transformation": transformation,
        "semantic_value_comparison": {
            "original_horizon_tokens": raw.count('"horizon_min"'),
            "repaired_horizon_tokens": repaired.count('"horizon_min"'),
            "original_and_repaired_normalized_values_equal": normalized == reparsed,
            "repaired_horizons": [stage["horizon_min"] for stage in reparsed["path"]],
        },
        "raw_output_modified": False,
    })
    write_json(out / "normalized_forecast_result.json", {
        "forecast_call_id": TARGET,
        "normalized_output": reparsed,
        "normalized_output_hash": digest(reparsed),
        "parse_audit": repaired_audit,
        "strict_parse": "PASSED",
        "strict_contract_validation": "PASSED",
        "contract_prediction": prediction,
        "contract_paths": paths,
    })
    write_json(out / "authority_decision.json", {
        "forecast_call_id": TARGET,
        "original_execution_run": SOURCE_RUN.name,
        "original_terminal_state": failure["terminal_state"],
        "provider_authority": authority,
        "pack_binding": {
            "batch_id": manifest["batch_id"],
            "pack_type": manifest["pack_type"],
            "pack_row_identity": manifest["pack_row_identity"],
            "pack_row_fingerprint": manifest["pack_row_fingerprint"],
        },
        "prompt_binding": {
            "prompt_version": manifest["migration_resume_key"]["prompt_version"],
            "prompt_instruction_fingerprint": manifest["prompt_instruction_fingerprint"],
            "prompt_text_fingerprint": manifest["migration_resume_key"]["prompt_text_fingerprint"],
        },
        "cutoff": manifest["historical_cutoff"],
        "leakage_control": "PASSED",
        "recovered_result_authoritative": True,
        "selection_reason": "EXISTING_PRESERVED_PROVIDER_PAYLOAD_RECOVERED_BY_DETERMINISTIC_STRUCTURAL_BOUNDARY_REPAIR",
        "duplicate_result_created": False,
    })
    full = json.loads((FULL_RUN / "full_completion_record.json").read_text())
    partition = json.loads((FULL_RUN / "identity_partition.json").read_text())
    write_json(out / "full_forecast_reconciliation.json", {
        "source_full_completion": FULL_RUN.name,
        "frozen_calls": full["frozen_forecast_calls"],
        "completed_attempted_calls": full["completed_attempted_calls"],
        "authoritative_valid_forecasts": full["authoritative_valid_forecasts"] + 1,
        "unrecovered_terminal_invalid_calls": [
            "FCL_27720b8b23236b173b96fdee",
            "FCL_7f0463b134c67757968580e8",
            "FCL_e07264654e9d3da6f63088a1",
        ],
        "terminal_invalid_completed_calls": 3,
        "unexecuted_calls": 0,
        "remote_state_unknown_calls": 0,
        "unresolved_authoritative_identities": 0,
        "pack_a": {"calls": partition["pack_a"]["calls"], "authoritative_valid": partition["pack_a"]["valid"] + 1, "terminal_invalid": 2},
        "pack_e": partition["pack_e"],
        "partition_complete": True,
    })
    print(json.dumps({"run_id": RUN_ID, "recovered": TARGET, "output": str(out)}, indent=2))


if __name__ == "__main__":
    main()
