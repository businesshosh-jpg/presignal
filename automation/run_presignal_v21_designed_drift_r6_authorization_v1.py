"""Materialize the bounded R6 paired Pack A/E authorization contract.

This module is deliberately offline.  It binds accepted Route B proof evidence
and records only authority that is present in the repository.  It never loads
credentials, selects an Event, acquires information, dispatches a provider, or
writes to Google.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from automation import run_presignal_v21_move5_freeze_v1 as freeze


AUTHORIZATION_NAME = "PRESIGNAL_V21_DESIGNED_DRIFT_2_R6_PAIRED_SMOKE_AUTHORIZATION_V1"
FREEZE_NAME = "PRESIGNAL_V21_ROUTE_B_CAPABILITY_FREEZE_V1"
FREEZE_FINGERPRINT = "sha256:8c910a343515d88ca63ce4aaf738f28f9b4a8ab22665397077858bfaf7e866e4"
DECISION = "R6_AUTHORIZATION_BLOCKED_APPROVED_SOURCE_ENVIRONMENT_UNRESOLVED"
EXTERNAL_ACCESS = {
    "provider_calls": 0,
    "google_calls": 0,
    "apps_script_calls": 0,
    "http_calls": 0,
    "market_data_calls": 0,
    "production_writes": 0,
    "historical_mutations": 0,
    "forecast_calls": 0,
    "outcome_operations": 0,
    "evaluation_operations": 0,
}


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def _read(relative: str) -> Any:
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


def _file_sha(relative: str) -> str:
    return "sha256:" + hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()


def _freeze_binding() -> dict[str, Any]:
    value = freeze.build_freeze()
    if value["fingerprint"] != FREEZE_FINGERPRINT:
        raise ValueError("ROUTE_B_FREEZE_FINGERPRINT_MISMATCH")
    if value["identity"]["freeze_name"] != FREEZE_NAME:
        raise ValueError("ROUTE_B_FREEZE_NAME_MISMATCH")
    historical = value["historical"]
    native = value["native"]
    if not historical["exact_fingerprint_match"]:
        raise ValueError("MOVE4B_PROOF_NOT_BOUND")
    if native["decision"] != "NATIVE_PROSPECTIVE_EPISODE_TO_PACK_CONTRACT_VALIDATED_MOVE_5_READY":
        raise ValueError("MOVE4C_PROOF_NOT_BOUND")
    return {
        "freeze_name": FREEZE_NAME,
        "freeze_fingerprint": FREEZE_FINGERPRINT,
        "freeze_manifest_path": "outputs/presignal_v21_designed_drift_move5/MOVE5-20260723-route-b-capability-freeze/route_b_capability_freeze_manifest.json",
        "freeze_manifest_checksum": _file_sha("outputs/presignal_v21_designed_drift_move5/MOVE5-20260723-route-b-capability-freeze/route_b_capability_freeze_manifest.json"),
        "implementation_commit": value["identity"]["implementation_commit"],
        "dependency_closure_complete": True,
        "move4b_expected_fingerprint": historical["expected_fingerprint"],
        "move4b_actual_fingerprint": historical["actual_fingerprint"],
        "move4b_exact_match": historical["exact_fingerprint_match"],
        "move4c_decision": native["decision"],
        "move4c_native_validation_checksum": native["checksums"]["native_validation"],
    }


def _episode_scope() -> dict[str, Any]:
    return {
        "authorized_episode_count": 1,
        "episode_type": "one upcoming prospective canonical Event Episode",
        "selection_source": "caller-selected from the existing authoritative prospective Episode source",
        "selection_execution": "REQUIRES_SEPARATE_R6_EXECUTION_TASK",
        "historical_episode_permitted": False,
        "synthetic_episode_permitted": False,
        "batch_episode_selection_permitted": False,
        "required_fields": ["episode_id", "primary_event_id", "release_ts", "forecast_cutoff_ts", "market/session lineage", "schema_version", "complete Event lineage"],
        "cutoff_requirement": "forecast cutoff must remain open when acquisition and forecast sequence begins",
        "stop_conditions": ["Episode count is not exactly one", "Episode identity missing", "Episode lineage contradiction", "Episode cutoff passed"],
    }


def _provider_scope() -> dict[str, Any]:
    return {
        "provider": "Gemini",
        "model": "gemini-2.5-flash-lite",
        "experimental_arms": ["Pack A", "Pack E"],
        "forecast_call_count": 2,
        "calls_per_arm": 1,
        "retry_count": 0,
        "fallback_provider_permitted": False,
        "provider_substitution_permitted": False,
        "model_substitution_permitted": False,
        "automatic_retries_permitted": False,
        "deterministic_call_order": ["Pack A", "Pack E"],
        "provider_request_scope": "shared union of accepted selected-provider Requests; this does not expand forecast-provider authorization",
    }


def _source_environment() -> dict[str, Any]:
    return {
        "authorization_status": "UNRESOLVED",
        "blocking_code": "R6_AUTHORIZATION_BLOCKED_APPROVED_SOURCE_ENVIRONMENT_UNRESOLVED",
        "environment_identity": None,
        "source_identities": [],
        "source_types": [],
        "source_keys_or_domains": [],
        "authoritative_configuration_path": None,
        "authoritative_commit": None,
        "checksum": None,
        "evidence_reviewed": [
            {"path": "contracts/presignal_v21_event_path/pack_capability_dependency_manifest.json", "finding": "core compute requires caller-supplied authorized source environment; it does not select one"},
            {"path": "outputs/presignal_v21_designed_drift_move4c/MOVE4C-20260723-native-contract-validation/native_fixture_inputs.json", "finding": "MOVE4C_APPROVED_SOURCES_V1 is explicitly a NATIVE_CONTRACT_VALIDATION_FIXTURE, not live R6 authority"},
            {"path": "git:e5a0ff288eb1f6fc228936cb1c693ed2bb2ab80f:automation/approved_knowledge_source_registry_v0.py", "finding": "historical registry provenance only; dependency manifest does not bind it as a prospective R6 source environment"},
            {"path": "outputs/presignal_v21_designed_drift_move5/MOVE5-20260723-route-b-capability-freeze/r6_authorized_boundary.json", "finding": "Move 5 explicitly left source environment and sources requiring R6 authorization"},
        ],
        "required_next_evidence": "one immutable approved-source environment already bound to prospective R6, with source identities, source types, source keys/domains, configuration commit, and checksum",
    }


def _google_read_scope() -> dict[str, Any]:
    return {
        "authorization_status": "UNRESOLVED",
        "spreadsheet_identity": None,
        "workbook_name": None,
        "sheet_or_object_scope": [],
        "adapter_entry_point": "existing Google adapter only; exact entry point requires an authoritative R6 target",
        "permitted_purpose": ["selected Episode input", "accepted Attention input", "existing canonical Pack A input components", "approved-source or execution configuration"],
        "prohibited": ["broad workbook inspection", "credential diagnostics", "Script Property inspection", "unrelated sheet reads", "historical workbook repair", "production reconciliation"],
        "evidence_reviewed": [
            {"path": "outputs/presignal_v21_designed_drift_move5/MOVE5-20260723-route-b-capability-freeze/r6_authorized_boundary.json", "finding": "Google read scope was unresolved"},
            {"path": "automation/presignal_v21_autonomous_ai_benchmark_v1.py", "finding": "legacy benchmark workbook constant is not an R6 Episode/Attention/Pack-A target binding"},
        ],
        "required_next_evidence": "one authoritative R6 input target with spreadsheet identity, object/range, and adapter entry point",
    }


def _google_write_scope() -> dict[str, Any]:
    return {
        "authorization_status": "UNRESOLVED",
        "spreadsheet_identity": None,
        "workbook_name": None,
        "sheet_or_table_destination": None,
        "writer_entry_point": None,
        "maximum_successful_write_count": 1,
        "failed_run_write_policy": "no Google write unless a failed-run schema is separately proven at the same explicit destination",
        "allowed_payload": ["R6 run identity", "Episode identity", "provider/model", "Pack A identity and checksum", "Pack E identity and checksum", "paired comparability report", "provider call metadata", "raw provider responses", "normalized forecasts", "lineage", "failure status", "authorization identity", "freeze identity"],
        "prohibited_payload": ["Outcome", "evaluation", "accuracy result", "production forecast promotion", "historical backfill", "unrelated diagnostics"],
        "evidence_reviewed": [
            {"path": "outputs/presignal_v21_designed_drift_move5/MOVE5-20260723-route-b-capability-freeze/r6_authorized_boundary.json", "finding": "writer destination was unresolved"},
            {"path": "automation/run_presignal_v21_designed_drift_r6_admission_v1.py", "finding": "isolated local admission snapshot root is not a Google paired-forecast evidence writer"},
            {"path": "automation/presignal_v21_autonomous_ai_benchmark_v1.py", "finding": "legacy benchmark writes Outcome_Comparison and is not a valid R6 paired-smoke destination"},
        ],
        "required_next_evidence": "one existing R6 evidence destination, write schema, writer entry point, and write-isolation rule bound by repository configuration",
    }


def _paired_arm_contract() -> dict[str, Any]:
    return {
        "same_episode": True,
        "same_provider": True,
        "same_model": True,
        "same_forecast_cutoff": True,
        "same_forecast_target": True,
        "same_prompt_version": True,
        "same_output_schema": True,
        "same_directional_label_contract": True,
        "same_forecast_horizon": True,
        "same_primary_endpoint_definition": True,
        "same_call_parameters": True,
        "same_temperature_or_equivalent": True,
        "pack_a_input": "canonical Pack A only",
        "pack_e_input": "canonical Pack E only",
        "only_intentional_difference": "input Pack",
        "pre_call_requirement": "construct and validate both Packs, freeze both arm inputs, and verify comparability before either forecast call",
    }


def _stop_policy() -> dict[str, Any]:
    return {
        "policy": "FAIL_CLOSED",
        "conditions": [
            "freeze fingerprint mismatch", "Episode count is not exactly one", "Episode identity missing", "Episode cutoff passed", "Episode lineage contradiction", "accepted selected Attention missing", "Attention provider/model mismatch", "provider authorization mismatch", "model authorization mismatch", "Request lineage incomplete", "approved-source environment unresolved", "acquisition source unapproved", "acquisition record post-cutoff", "acquisition timestamp missing", "acquisition Request lineage mismatch", "acquisition Episode lineage mismatch", "Pack A construction failure", "Pack E validation failure", "Pack E computation failure", "paired comparability failure", "Google read target mismatch", "Google write target mismatch", "evidence schema mismatch", "provider-call budget would exceed two", "any retry is attempted", "Outcome or evaluation boundary is reached",
        ],
        "pre_call_failure_provider_calls": 0,
        "incomplete_pair_policy": "if Pack A call succeeds and Pack E call fails, do not retry; record incomplete only at an authorized failed-run destination and never promote a completed comparison",
        "partial_pack_success_permitted": False,
    }


def build_authorization() -> dict[str, Any]:
    binding = _freeze_binding()
    episode = _episode_scope()
    provider = _provider_scope()
    acquisition = {
        "sequence_count": 1,
        "retry_acquisition_permitted": False,
        "historical_backfill_permitted": False,
        "autonomous_recurrence_permitted": False,
        "unrelated_browsing_permitted": False,
        "approved_source_environment": _source_environment(),
        "required_record_fields": ["acquisition_record_identity", "originating_request_identity", "episode_identity", "source_identity", "source_url_or_key", "source_type", "retrieval_timestamp", "as_of_timestamp", "forecast_cutoff", "raw_acquired_content", "normalized_acquired_content", "acquisition_method", "availability_state", "approved_source_state"],
        "post_cutoff_records_permitted": False,
        "unapproved_sources_permitted": False,
        "missing_source_lineage_permitted": False,
    }
    read_scope = _google_read_scope()
    write_scope = _google_write_scope()
    paired = _paired_arm_contract()
    budget = {"provider": provider["provider"], "model": provider["model"], "arm_calls": {"Pack A": 1, "Pack E": 1}, "total_forecast_calls": 2, "retry_count": 0, "third_call_permitted": False, "provider_substitution_permitted": False, "model_substitution_permitted": False}
    prohibitions = {"outcome_construction": "PROHIBITED", "market_path_collection": "PROHIBITED except only as needed to identify Episode before cutoff", "evaluation": "PROHIBITED", "accuracy_comparison": "PROHIBITED", "winner_declaration": "PROHIBITED", "production_promotion": "PROHIBITED"}
    stop = _stop_policy()
    identity = {
        "authorization_name": AUTHORIZATION_NAME,
        "schema_version": "1",
        "route_b_freeze": binding,
        "episode_scope": episode,
        "provider_scope": provider,
        "acquisition_scope": acquisition,
        "google_read_scope": read_scope,
        "google_write_scope": write_scope,
        "paired_arm_contract": paired,
        "provider_call_budget": budget,
        "outcome_evaluation_prohibition": prohibitions,
        "failure_stop_policy": stop,
    }
    return {"identity": identity, "fingerprint": sha(identity), "reports": {
        "authorized_episode_scope.json": episode,
        "authorized_provider_scope.json": provider,
        "authorized_acquisition_scope.json": acquisition,
        "authorized_google_read_scope.json": read_scope,
        "authorized_google_write_scope.json": write_scope,
        "authorized_evidence_destination.json": {"authorization_status": "UNRESOLVED", "destination_identity": None, "authoritative_source": None, "write_schema": None, "write_isolation_status": "UNRESOLVED", "reason": "no existing R6 paired-smoke Google evidence destination is bound by repository evidence", "required_next_evidence": write_scope["required_next_evidence"]},
        "paired_arm_contract.json": paired,
        "provider_call_budget.json": budget,
        "failure_stop_policy.json": stop,
        "outcome_evaluation_prohibition.json": prohibitions,
        "r6_authorization_manifest.json": identity,
        "r6_authorization_fingerprint.json": {"authorization_name": AUTHORIZATION_NAME, "authorization_fingerprint": sha(identity), "canonicalization": "sorted-key compact UTF-8 JSON SHA-256", "reproducible": True},
        "final_authorization_decision.json": {"decision": DECISION, "execution_authorized": False, "r6_executed": False, "primary_blocker": "no immutable approved-source environment is bound to prospective R6 in the repository", "additional_unresolved_live_boundaries": ["Google read target", "Google write target", "Google evidence destination"], "external_access": EXTERNAL_ACCESS},
    }}


def write_reports(output: Path, values: Mapping[str, Any]) -> None:
    output.mkdir(parents=True, exist_ok=True)
    for name, value in values.items():
        (output / name).write_text(canonical(value) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    value = build_authorization()
    write_reports(args.output, value["reports"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
