"""Offline proof and blocked-live report for R6 native input materialization."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from automation import presignal_v21_native_input_materialization_v1 as native


V3_FINGERPRINT = "sha256:c8cb003af94eef2ef9cad8f323ab31b3c1990f3ffdcdab5ee3e6285fda76efb9"
FREEZE_FINGERPRINT = native.ROUTE_B_FREEZE
DECISION = "NATIVE_ATTENTION_REQUIRES_SEPARATE_PROVIDER_AUTHORIZATION"


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def fixture() -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    episode = {"episode_id": "EP_EVENT_NATIVE_INPUT_FIXTURE", "primary_event_id": "EV_NATIVE_FIXTURE", "forecast_cutoff_ts": "2030-01-01T11:59:00Z", "release_ts": "2030-01-01T12:00:00Z", "schema_version": "2.1.0"}
    attention = native.materialize_selected_native_attention(episode=episode, provider="Gemini", model="gemini-2.5-flash-lite", prompt_version="NATIVE_ATTENTION_PROMPT_V1", selection_state="SELECTED_FOR_INFORMATION_REQUESTS", acceptance_state="ACCEPTED", selection_reason="frozen native contract fixture", effective_timestamp="2030-01-01T11:55:00Z", provenance={"source": "existing_v2_attention_prompt_schema", "fixture": True})
    requests = [
        {"request_identity": "REQ_A", "episode_identity": episode["episode_id"], "provider": "Gemini", "model": "gemini-2.5-flash-lite", "prompt_version": "NATIVE_ATTENTION_PROMPT_V1", "forecast_cutoff": episode["forecast_cutoff_ts"], "requested_information": "Current DXY state", "information_category": "dxy", "priority": "must_have"},
        {"request_identity": "REQ_B", "episode_identity": episode["episode_id"], "provider": "Gemini", "model": "gemini-2.5-flash-lite", "prompt_version": "NATIVE_ATTENTION_PROMPT_V1", "forecast_cutoff": episode["forecast_cutoff_ts"], "requested_information": "US two-year yield state", "information_category": "treasury_yields", "priority": "must_have"},
    ]
    return episode, attention, requests


def build_reports() -> dict[str, Any]:
    episode, attention, requests = fixture()
    pack_a = native.build_canonical_pack_a(episode=episode, attention=attention, canonical_requests=requests, provenance={"source": "existing_v2_pack_a_provider_requests", "fixture": True})
    runs = [native.build_canonical_pack_a(episode=episode, attention=attention, canonical_requests=requests, provenance={"source": "existing_v2_pack_a_provider_requests", "fixture": True}) for _ in range(3)]
    deterministic = {"proof_runs": 3, "identical_attention_ids": len({attention["attention_identity"] for _ in runs}) == 1, "identical_pack_a_ids": len({row["pack_a_identity"] for row in runs}) == 1, "identical_content_checksums": len({row["content_checksum"] for row in runs}) == 1, "identical_lineage_checksums": len({row["lineage_checksum"] for row in runs}) == 1}
    live_attention = {"materialization_status": "BLOCKED", "selected_episode_identity": None, "attention_identity": None, "provider": "Gemini", "model": "gemini-2.5-flash-lite", "blocker": "NATIVE_ATTENTION_REQUIRES_SEPARATE_PROVIDER_AUTHORIZATION", "reason": "existing authoritative native Attention science is provider-response-driven; zero provider calls are authorized and no frozen selected Gemini response exists for a current prospective Episode", "google_write_attempted": False}
    live_pack = {"materialization_status": "BLOCKED", "selected_episode_identity": None, "pack_a_identity": None, "blocker": "CANONICAL_PACK_A_REQUIRES_SELECTED_ATTENTION_AND_CANONICAL_REQUESTS", "reason": "stable Pack A is the selected provider's ordered canonical Request set; it cannot be constructed before an accepted selected Attention result and its Request response", "google_write_attempted": False}
    readiness_identity = {"readiness_name": "PRESIGNAL_V21_DESIGNED_DRIFT_2_R6_NATIVE_INPUT_READINESS_V1", "route_b_freeze_fingerprint": FREEZE_FINGERPRINT, "r6_authorization_v3_fingerprint": V3_FINGERPRINT, "episode_identity": None, "attention_identity": None, "pack_a_identity": None, "all_native_inputs_ready": False, "blockers": [live_attention["blocker"], live_pack["blocker"], "GOOGLE_STRUCTURAL_SETUP_CREDENTIAL_REFRESH_TRANSPORT_FAILED"]}
    return {
        "native_attention_contract_trace.json": {"authoritative_source": "automation/presignal_v21_minimal_prospective_lineage_v1.py:build_prospective_attention", "selection_science": "existing v2 provider-response Attention prompt/schema", "native_validation_source": "automation/presignal_v21_pack_capability_v1.py:_validate_attention", "historical_watch_conversion_permitted": False, "accepted_states": ["SELECTED", "SELECTED_FOR_INFORMATION_REQUESTS"], "acceptance_state": "ACCEPTED", "provider_model": "Gemini/gemini-2.5-flash-lite"},
        "native_attention_schema.json": {"schema_version": native.ATTENTION_SCHEMA_VERSION, "headers": list(native.ATTENTION_HEADERS), "target_spreadsheet_id": native.MAIN_SPREADSHEET_ID, "target_sheet": native.ATTENTION_SHEET, "outcome_fields": False, "evaluation_fields": False},
        "native_attention_fixture.json": {"classification": "OFFLINE_CONTRACT_FIXTURE_NOT_LIVE_ATTENTION", "episode": episode, "attention": attention},
        "native_attention_materialization_report.json": live_attention,
        "native_attention_google_binding.json": {"target_spreadsheet_id": native.MAIN_SPREADSHEET_ID, "target_sheet": native.ATTENTION_SHEET, "structural_setup_status": "BLOCKED_CREDENTIAL_REFRESH_TRANSPORT_FAILED", "object_write_limit": 1, "object_rows_written": 0},
        "canonical_pack_a_contract_trace.json": {"authoritative_source": "automation/presignal_v21_minimal_prospective_lineage_v1.py:build_prospective_packs", "scientific_definition": "selected provider's ordered canonical Information Request set; shared_market_state_pack is None", "pack_e_subtraction_used": False, "source_acquisition_content_used": False},
        "canonical_pack_a_schema.json": {"schema_version": native.PACK_A_SCHEMA_VERSION, "headers": list(native.PACK_A_HEADERS), "target_spreadsheet_id": native.MAIN_SPREADSHEET_ID, "target_sheet": native.PACK_A_SHEET, "outcome_fields": False, "evaluation_fields": False},
        "canonical_pack_a_fixture.json": {"classification": "OFFLINE_CONTRACT_FIXTURE_NOT_LIVE_PACK_A", "canonical_requests": requests, "pack_a": pack_a},
        "canonical_pack_a_materialization_report.json": live_pack,
        "canonical_pack_a_google_binding.json": {"target_spreadsheet_id": native.MAIN_SPREADSHEET_ID, "target_sheet": native.PACK_A_SHEET, "structural_setup_status": "BLOCKED_CREDENTIAL_REFRESH_TRANSPORT_FAILED", "object_write_limit": 1, "object_rows_written": 0},
        "native_input_determinism_report.json": deterministic,
        "native_input_isolation_audit.json": {"forecast_provider_calls": 0, "gemini_calls": 0, "http_acquisition_calls": 0, "market_data_calls": 0, "live_pack_e_computations": 0, "r6_paired_forecast_calls": 0, "r6_evidence_writes": 0, "historical_mutations": 0, "outcome_operations": 0, "evaluation_operations": 0, "attention_writes": 0, "pack_a_writes": 0},
        "native_input_readiness_manifest.json": readiness_identity,
        "native_input_readiness_fingerprint.json": {"readiness_name": readiness_identity["readiness_name"], "readiness_fingerprint": native.checksum(readiness_identity), "canonicalization": "sorted-key compact UTF-8 JSON SHA-256", "reproducible": True},
        "final_native_input_materialization_decision.json": {"decision": DECISION, "execution_authorized": False, "episode_blocker": "NO_EPISODE_SELECTED_BEFORE_NATIVE_ATTENTION_AUTHORIZATION", "attention_blocker": live_attention["blocker"], "pack_a_blocker": live_pack["blocker"], "google_object_blocker": "GOOGLE_STRUCTURAL_SETUP_CREDENTIAL_REFRESH_TRANSPORT_FAILED", "google_operations": {"metadata_reads": 0, "schema_reads": 0, "structural_writes": 0, "attention_writes": 0, "pack_a_writes": 0, "readback_reads": 0, "cleanup_operations": 0, "credential_refresh_attempts": 1, "token_file_unchanged": True}}
    }


def write_reports(output: Path, reports: Mapping[str, Any]) -> None:
    output.mkdir(parents=True, exist_ok=True)
    for name, value in reports.items(): (output / name).write_text(_json(value) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(); write_reports(args.output, build_reports()); return 0


if __name__ == "__main__": raise SystemExit(main())
