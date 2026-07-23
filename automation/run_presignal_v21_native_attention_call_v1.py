"""Write deterministic local evidence for the bounded R6 native Attention call."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from automation import presignal_v21_native_attention_call_v1 as call


OUTPUT = ROOT / "outputs" / "presignal_v21_designed_drift_r6_native_attention_call" / "R6-NATIVE-ATTENTION-20260723-v1"


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n", encoding="utf-8")


def pack_a_contract_verification() -> dict[str, Any]:
    return {"classification": "PACK_A_CONTRACT_CONFIRMED", "authoritative_source": "automation/presignal_v21_minimal_prospective_lineage_v1.py:build_prospective_packs", "current_implementation_description": "selected provider's ordered canonical Information Request set", "exact_governing_definition": "pack_a_by_provider[provider] contains the provider's parsed information_requests in supplied canonical order; shared_market_state_pack is None; its fingerprint hashes provider plus ordered request identities.", "included_information": "provider-owned canonical Information Requests only", "excluded_information": ["shared_market_state_pack", "acquired source content", "Pack E request/source lineage"], "relationship_to_pack_e": "Pack E is separately one shared market-state pack; Pack A is not Pack E minus information.", "cutoff_behavior": "information_cutoff_ts is bound on the Pack A envelope and each Request lineage.", "scientific_mismatch_found": False, "later_repair_required": False}


def blocked_reports(*, candidate_read: Mapping[str, Any]) -> dict[str, Any]:
    selection = call.select_single_eligible_episode(candidate_read.get("candidates", []), as_of_utc=str(candidate_read["read_timestamp_utc"]))
    decision = selection["decision"]
    not_executed = {"status": "NOT_EXECUTED", "reason": decision, "provider_calls": 0, "retries": 0}
    audit = {"google_episode_reads": 1, "gemini_attention_calls": 0, "other_provider_calls": 0, "forecast_calls": 0, "http_acquisition_calls": 0, "market_data_calls": 0, "live_pack_e_computations": 0, "google_scientific_writes": 0, "r6_evidence_writes": 0, "historical_mutations": 0, "outcome_operations": 0, "evaluation_operations": 0}
    return {
        "native_attention_call_authorization.json": call.authorization_manifest(),
        "native_attention_call_authorization_fingerprint.json": {"authorization_name": call.AUTHORIZATION_NAME, "authorization_fingerprint": call.checksum(call.authorization_manifest()), "canonicalization": "sorted-key compact UTF-8 JSON SHA-256", "reproducible": True},
        "episode_candidate_inventory.json": {"spreadsheet_id": candidate_read["spreadsheet_id"], "object": candidate_read["range"], "read_timestamp_utc": candidate_read["read_timestamp_utc"], "candidate_window_row_count": candidate_read["candidate_count"], "eligible_candidate_count": candidate_read["eligible_count"], "candidates": selection["eligible_candidates"], "rejection_summary": {"NOT_UPCOMING": candidate_read["candidate_count"] - candidate_read["eligible_count"]}, "token_file_checksum_before": candidate_read["token_checksum_before"], "token_file_checksum_after": candidate_read["token_checksum_after"]},
        "episode_selection_report.json": {"decision": decision, "selection_rule": selection.get("selection_rule", "No eligible prospective canonical Episode in the bounded candidate window."), "selected_episode": selection["selected_episode"], "eligible_candidate_count": len(selection["eligible_candidates"]), "provider_calls_before_selection": 0},
        "attention_pre_call_manifest.json": not_executed,
        "attention_raw_response.json": not_executed,
        "attention_normalized_response.json": not_executed,
        "native_attention_object.json": not_executed,
        "attention_validation_report.json": {**not_executed, "schema_validation": "NOT_EXECUTED"},
        "attention_determinism_report.json": {"status": "NOT_EXECUTED_NO_VALID_LIVE_RESPONSE", "proof_runs": 0, "reason": decision},
        "pack_a_contract_verification.json": pack_a_contract_verification(),
        "external_access_audit.json": audit,
        "final_native_attention_decision.json": {"decision": decision, "call_attempted": False, "call_count": 0, "selected_episode_identity": None, "attention_identity": None, "pack_a_contract_classification": "PACK_A_CONTRACT_CONFIRMED", "token_file_unchanged": candidate_read["token_checksum_before"] == candidate_read["token_checksum_after"]},
    }


def write_reports(output: Path, reports: Mapping[str, Any]) -> None:
    for name, report in reports.items(): write_json(output / name, report)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate-read", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    write_reports(args.output, blocked_reports(candidate_read=json.loads(args.candidate_read.read_text(encoding="utf-8"))))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
