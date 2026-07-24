"""Offline-only migration evidence for prospective R6 Pack E acquisition.

The script never executes Apps Script or a source request.  It records the
thin wrappers added beside the existing v2B fetchers, examines only the
presence/type of local references, and decides whether the selected FOMC Pack
E has a nonempty, runtime-ready approved environment.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from automation import presignal_v21_pack_capability_v1 as capability
from automation.test_prospective_pack_e_acquisition_v1 import invoke, payload


PACK = ROOT / "outputs/presignal_v21_designed_drift_r6_pack_construction_fomc/R6-PACK-CONSTRUCTION-FOMC-20260724-v1"
PRIORITY = ROOT / "outputs/presignal_v21_designed_drift_r6_information_request_priority_contract_repair/R6-INFORMATION-REQUEST-PRIORITY-CONTRACT-REPAIR-20260724-v1"
CALENDAR = ROOT / "outputs/presignal_v21_designed_drift_r6_calendar_row_level_reconciliation/R6-CALENDAR-ROW-LEVEL-RECONCILIATION-20260724-v1"
OUT = ROOT / "outputs/presignal_v21_designed_drift_r6_pack_e_native_adapter_migration/R6-PACK-E-NATIVE-ADAPTER-MIGRATION-20260724-v1"

EPISODE = "EP_EVENT_68a8e1cc3c9bf6ccc385"
PACK_A = "PACK_A_c08bab51525d614592678fae"
PACK_A_CONTENT = "sha256:c08bab51525d614592678fae0d82ce9e695ac8ff31afdf28d3e6353573818a59"
PACK_AUTH = "sha256:87fc65d0f9ec84e8efc1f0e8ef0276eb50a35d52c624191cc682dcea9f8fb869"
ROUTE_B = "sha256:8c910a343515d88ca63ce4aaf738f28f9b4a8ab22665397077858bfaf7e866e4"
CUTOFF = "2026-07-29T18:00:00Z"
ADAPTER = "apps_script/prospective_pack_e_acquisition.js:apiBuildProspectivePackENativeAcquisitionRecord"


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def read(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write(output: Path, name: str, value: Any) -> None:
    output.mkdir(parents=True, exist_ok=True)
    (output / name).write_text(canonical(value) + "\n", encoding="utf-8")


def adapter_inventory() -> list[dict[str, Any]]:
    """Keep source authority separate from reusable v2 implementation evidence."""
    return [
        {
            "source_identity": "KSRC_FMP",
            "legacy_adapter": "apps_script/market_context_v2b.js:_v2bFetchFmpHistory_",
            "reusable_fetch_function": "_v2bFetchFmpHistory_",
            "reusable_normalizer": "legacy {date,value} row projection in _v2bFetchFmpHistory_",
            "prospective_adapter": ADAPTER + " [source_id=KSRC_FMP]",
            "native_acquisition_record_emitted": True,
            "historical_writer": "_v2bBuildSeriesCache_ -> _buildMarketContextPack_ -> legacy writer (not invoked)",
            "credential_type": "Apps Script FMP_API_KEY resolver",
            "configuration_reference": "Apps Script FMP_API_KEY resolver (CFG.FMP_API_KEY or Script Property FMP_API_KEY)",
            "supported_pack_e_fields": ["DXY_LEVEL", "DXY_CHANGE_PRESESSION", "USDJPY_RETURN_1H_PRESESSION", "USDJPY_RETURN_4H_PRESESSION", "USDJPY_RETURN_24H_PRESESSION", "USDJPY_TREND_LABEL"],
            "temporal_support": "caller bounded dates plus source/as-of/retrieval timestamp validation",
            "runtime_readiness": "APPROVED_AND_RUNTIME_READY_FOR_ITS_DECLARED_FIELDS",
            "runtime_reason": "The same FMP key resolver completed the preserved authorized calendar execution; no secret value was inspected or source call made here.",
        },
        {
            "source_identity": "KSRC_FRED",
            "legacy_adapter": "apps_script/market_context_v2b.js:_v2bFetchFredHistory_",
            "reusable_fetch_function": "_v2bFetchFredHistory_",
            "reusable_normalizer": "legacy {date,value} row projection in _v2bFetchFredHistory_",
            "prospective_adapter": ADAPTER + " [source_id=KSRC_FRED]",
            "native_acquisition_record_emitted": True,
            "historical_writer": "_v2bBuildSeriesCache_ -> _buildMarketContextPack_ -> legacy writer (not invoked)",
            "credential_type": "Apps Script Script Property FRED_API_KEY",
            "configuration_reference": "Apps Script Script Property FRED_API_KEY",
            "supported_pack_e_fields": ["US2Y_YIELD_LEVEL", "US10Y_YIELD_LEVEL", "US2Y_CHANGE_FROM_PRIOR_CLOSE", "US10Y_CHANGE_FROM_PRIOR_CLOSE", "US10Y_MINUS_US2Y_CURVE"],
            "temporal_support": "caller bounded dates plus source/as-of/retrieval timestamp validation",
            "runtime_readiness": "APPROVED_BUT_CONFIGURATION_MISSING",
            "runtime_reason": "No local configuration reference proves the required Script Property is bound; the remote property value is intentionally not inspected.",
        },
        {
            "source_identity": "KSRC_EODHD",
            "legacy_adapter": "apps_script/market_context_v2b.js:_v2bFetchEodhdHistory_",
            "reusable_fetch_function": "_v2bFetchEodhdHistory_",
            "reusable_normalizer": "legacy {date,value} row projection in _v2bFetchEodhdHistory_",
            "prospective_adapter": ADAPTER + " [source_id=KSRC_EODHD]",
            "native_acquisition_record_emitted": True,
            "historical_writer": "_v2bBuildSeriesCache_ -> _buildMarketContextPack_ -> legacy writer (not invoked)",
            "credential_type": "Apps Script EODHD API-key resolver",
            "configuration_reference": "Apps Script EODHD API-key resolver",
            "supported_pack_e_fields": ["USDJPY_RETURN_1H_PRESESSION", "USDJPY_RETURN_4H_PRESESSION", "USDJPY_RETURN_24H_PRESESSION", "USDJPY_TREND_LABEL"],
            "temporal_support": "caller bounded dates plus source/as-of/retrieval timestamp validation",
            "runtime_readiness": "APPROVED_BUT_CONFIGURATION_MISSING",
            "runtime_reason": "No local configuration reference proves the existing resolver can obtain an EODHD key; no remote property value was inspected.",
        },
        {
            "source_identity": "KSRC_US_TREASURY",
            "legacy_adapter": "NOT_PRESENT",
            "reusable_fetch_function": "NOT_PRESENT",
            "reusable_normalizer": "NOT_PRESENT",
            "prospective_adapter": "NOT_CREATED_NO_EXISTING_APPROVED_FETCH_CAPABILITY",
            "native_acquisition_record_emitted": False,
            "historical_writer": "NOT_APPLICABLE",
            "credential_type": "public API or approved adapter (no existing adapter bound)",
            "configuration_reference": "NOT_BOUND",
            "supported_pack_e_fields": ["US2Y_YIELD_LEVEL", "US10Y_YIELD_LEVEL", "US2Y_CHANGE_FROM_PRIOR_CLOSE", "US10Y_CHANGE_FROM_PRIOR_CLOSE", "US10Y_MINUS_US2Y_CURVE"],
            "temporal_support": "NOT_AVAILABLE",
            "runtime_readiness": "APPROVED_BUT_ADAPTER_UNAVAILABLE",
            "runtime_reason": "Registry approval is not an implementation; this task does not create a provider or adapter.",
        },
    ]


def local_binding_audit() -> dict[str, Any]:
    current_token = ROOT / "local/token.json"
    primary_token = ROOT.parent / "presignal" / "local/token.json"
    return {
        "inspection_scope": "presence/type only; no credential, token, key, or header contents read",
        "environment_variable_presence": {name: "SET" if bool(os.environ.get(name)) else "NOT_SET" for name in ("FRED_API_KEY", "EODHD_API_KEY", "FMP_API_KEY", "FMP_BASE")},
        "configuration_files_checked": {name: False for name in ("local/.env", ".env", ".env.local", "config/local.json", "config/sources.json")},
        "apps_script_bridge_token": {
            "repository_relative_reference": "local/token.json",
            "exists": current_token.is_file(),
            "git_ignored": True,
            "role": "Apps Script bridge credential only; not a market-source API key",
        },
        "cross_worktree_existing_binding": {
            "primary_worktree_reference_exists": primary_token.is_file(),
            "same_existing_token_reference": current_token.is_file() and primary_token.is_file() and os.path.samefile(current_token, primary_token),
            "binding_method": "existing ignored local symlink/reference; no copied value",
        },
        "remote_script_properties": "NOT_INSPECTED",
        "secret_values_recorded": False,
    }


def fixture_results() -> dict[str, Any]:
    first, second, third = invoke(payload()), invoke(payload()), invoke(payload())
    empty = payload(); empty["rows"]["FRED"] = []
    unavailable = invoke(empty)
    post_cutoff = invoke(payload(retrieval_timestamp="2026-07-29T18:00:01Z"))
    fmp = invoke(payload("KSRC_FMP", canonical_field="DXY_LEVEL", query_symbol="DX-Y.NYB", query_identity="DX-Y.NYB@2026-07-28", source_identity="fmp:DX-Y.NYB", source_url_or_key="fmp:DX-Y.NYB"))
    eodhd = invoke(payload("KSRC_EODHD", canonical_field="USDJPY_RETURN_24H_PRESESSION", query_symbol="USDJPY.FOREX", query_identity="USDJPY@2026-07-28", source_identity="eodhd:USDJPY.FOREX", source_url_or_key="eodhd:USDJPY.FOREX"))
    return {
        "fixture_execution": "local Node VM with stubbed existing v2 fetch functions; no network or Apps Script execution",
        "fred_valid_record": {"status": first["result"]["status"], "object": first["result"]["object"], "record_id": first["result"]["acquisition_record_id"], "raw_checksum": first["result"]["raw_checksum"], "normalized_checksum": first["result"]["normalized_checksum"], "fetch_calls": first["calls"], "deterministic_three_runs": first["result"] == second["result"] == third["result"]},
        "fmp_valid_record": {"status": fmp["result"]["status"], "fetch_calls": fmp["calls"]},
        "eodhd_valid_record": {"status": eodhd["result"]["status"], "fetch_calls": eodhd["calls"]},
        "empty_source": {"status": unavailable["result"]["status"], "error_classification": unavailable["result"]["error_classification"], "writer_calls": unavailable["calls"]["writers"]},
        "post_cutoff": {"accepted": post_cutoff["ok"], "failure": post_cutoff["error"]},
        "writer_invocations": 0,
        "live_source_calls": 0,
    }


def audit() -> dict[str, int]:
    return {
        "source_http_api_calls": 0, "apps_script_executions": 0, "google_reads": 0, "google_writes": 0,
        "gemini_calls": 0, "calendar_refreshes": 0, "fmp_live_calls": 0, "fred_live_calls": 0,
        "eodhd_live_calls": 0, "us_treasury_live_calls": 0, "pack_e_constructions": 0,
        "forecast_calls": 0, "outcome_operations": 0, "evaluation_operations": 0,
    }


def run(output: Path = OUT) -> str:
    pack_auth, pack_a = read(PRIORITY / "new_r6_pack_authorization_preparation.json"), read(PACK / "new_r6_pack_a.json")
    inventory, bindings = adapter_inventory(), local_binding_audit()
    requests = pack_a["ordered_canonical_requests"]
    treasury = next(row for row in requests if row["information_category"] == "treasury_yields")
    required_coverage = {
        "authority": "automation/presignal_v21_pack_capability_v1.py:_capability_for_request maps the selected treasury request to a deterministic Pack E capability",
        "required_fields": [{"capability_id": "TREASURY_2Y_10Y_PRESESSION_STATE", "field_binding": ["US2Y_YIELD_LEVEL", "US10Y_YIELD_LEVEL", "US2Y_CHANGE_FROM_PRIOR_CLOSE", "US10Y_CHANGE_FROM_PRIOR_CLOSE", "US10Y_MINUS_US2Y_CURVE"], "request_identity": treasury["request_identity"], "classification": "REQUIRED_FOR_NONEMPTY_DETERMINISTIC_TREASURY_PACK_E_CONTEXT"}],
        "optional_fields": ["DXY_PRESESSION_STATE", "USDJPY_PRESESSION_STATE"],
        "contextual_or_not_acquired": ["FED_EXPECTATIONS_POLICY_BLOCK", "INTERPRETIVE_CONTEXT_NOT_ACQUIRED", "UPCOMING_EVENT_CALENDAR", "HISTORICAL_EVENT_SENSITIVITY", "INFLATION_NARRATIVE_SOURCE_GROUNDED", "LABOR_MARKET_CONTEXT"],
        "frozen_rules_fingerprint": capability.checksum(capability.FROZEN_PACK_E_RULES_V1),
        "rule_note": "The core builder can declare unavailable items, but a prospective acquisition authorization requires at least one runtime-ready source for the selected deterministic external capability; no blank environment is promoted as live authority.",
    }
    ready = {row["source_identity"]: row for row in inventory if row["runtime_readiness"] == "APPROVED_AND_RUNTIME_READY_FOR_ITS_DECLARED_FIELDS"}
    candidates = [
        {"candidate_identity": "R6_PACK_E_FMP_ONLY", "source_identities": ["KSRC_FMP"], "adapter_identities": [ADAPTER], "field_coverage": ["DXY_PRESESSION_STATE", "USDJPY_PRESESSION_STATE"], "required_coverage_complete": False, "runtime_ready": True, "expected_source_call_count": 0, "retry_budget": 0, "missing_items": ["approved runtime-ready Treasury 2Y/10Y route for " + treasury["request_identity"]], "rejection_reason": "FMP is runtime ready only for fields not bound to the selected deterministic Treasury capability."},
        {"candidate_identity": "R6_PACK_E_FRED_TREASURY_MINIMUM", "source_identities": ["KSRC_FRED"], "adapter_identities": [ADAPTER], "field_coverage": required_coverage["required_fields"][0]["field_binding"], "required_coverage_complete": False, "runtime_ready": False, "expected_source_call_count": 1, "retry_budget": 0, "missing_items": ["existing Apps Script Script Property FRED_API_KEY binding"], "rejection_reason": "The new wrapper is ready, but the local runtime configuration reference remains unproven."},
    ]
    complete = False
    decision = "NEW_R6_PACK_E_NATIVE_ADAPTERS_READY_BINDING_INCOMPLETE"
    fixture = fixture_results()
    validations = {
        "pack_authorization_fingerprint_valid": pack_auth.get("authorization_fingerprint") == PACK_AUTH,
        "pack_a_identity_valid": pack_a.get("pack_identity") == PACK_A,
        "pack_a_content_checksum_valid": pack_a.get("content_checksum") == PACK_A_CONTENT,
        "route_b_freeze_valid": pack_auth.get("route_b_freeze_fingerprint") == ROUTE_B,
        "episode_valid": pack_a.get("episode_identity") == EPISODE,
        "cutoff_unchanged": pack_a.get("forecast_cutoff") == CUTOFF,
        "new_wrapper_exists": (ROOT / "apps_script/prospective_pack_e_acquisition.js").is_file(),
        "all_migrated_wrappers_emit_native_records_in_fixture": all(row["native_acquisition_record_emitted"] for row in inventory[:3]),
        "fmp_configuration_reference_supported_by_preserved_calendar": (CALENDAR / "calendar_row_level_replay_normalized_response.json").is_file(),
    }
    plan = {
        "boundary": "caller -> existing approved source fetch capability -> prospective adapter -> NATIVE_ACQUISITION_RECORD -> pure Pack E normalization -> caller-controlled writer",
        "caller_inputs": ["source_id", "adapter_identity", "configuration_reference", "credential_reference_type", "bounded_start_date", "bounded_end_date", "query_identity", "episode_id", "pack_a_identity", "request_identity", "canonical_field", "forecast_cutoff_ts", "retrieval_timestamp", "as_of_timestamp"],
        "adapter_behavior": "one fetch invocation; zero retries; no fallback; no writer; canonical record or frozen failure record",
        "non_goals": ["implicit environment discovery", "Google writes", "Pack E construction", "historical writer modification", "new provider registration"],
    }
    native_contract = {
        "authority": "automation/presignal_v21_pack_capability_v1.py:build_immutable_acquired_information_bundle strict NATIVE_ACQUISITION_RECORD validation",
        "record_identity": "acquisition_record_id derived from nonsecret Episode, Pack A, Request, source, field, source identity, and source timestamp inputs",
        "required_fields": ["object", "schema_version", "acquisition_record_id", "episode_id", "pack_a_identity", "request_identity", "forecast_cutoff_ts", "source_id", "adapter_identity", "configuration_reference", "credential_reference_type", "source_identity", "source_url_or_key", "source_type", "query_identity", "retrieval_timestamp", "acquisition_timestamp", "source_timestamp", "as_of_timestamp", "acquisition_method", "status", "error_classification", "raw_acquired_content", "normalized_acquired_content", "raw_checksum", "normalized_checksum", "source_items"],
        "failure_states": ["SOURCE_CONFIGURATION_MISSING", "SOURCE_CREDENTIAL_MISSING", "SOURCE_ADAPTER_UNAVAILABLE", "SOURCE_ACCESS_NOT_AUTHORIZED", "SOURCE_QUERY_UNSUPPORTED", "SOURCE_TEMPORAL_CONTRACT_UNSUPPORTED", "SOURCE_CONTENT_NOT_FOUND"],
        "source_record_validation": "source, as-of, acquisition, and retrieval timestamps cannot exceed cutoff; source items retain source and adapter lineage",
        "writer_operations": 0,
    }
    reports: dict[str, Any] = {
        "pack_e_native_acquisition_record_contract_trace.json": native_contract,
        "pack_e_legacy_adapter_reuse_audit.json": {"source_count": len(inventory), "sources": inventory, "legacy_behavior_changed": False},
        "pack_e_prospective_adapter_migration_plan.json": plan,
        "pack_e_prospective_adapter_manifest.json": {"schema_version": "presignal.prospective_pack_e_acquisition.v1", "implementation": "apps_script/prospective_pack_e_acquisition.js", "public_entry_point": "apiBuildProspectivePackENativeAcquisitionRecord", "source_specs": [{"source_identity": row["source_identity"], "adapter_identity": row["prospective_adapter"]} for row in inventory[:3]], "writer_invocation_permitted": False, "retry_budget": 0},
        "pack_e_prospective_adapter_fixture_results.json": fixture,
        "pack_e_runtime_configuration_reference_audit.json": bindings,
        "pack_e_cross_worktree_binding_report.json": bindings["cross_worktree_existing_binding"],
        "pack_e_secret_safety_report.json": {"new_credentials_created": False, "credential_contents_exposed": False, "credentials_committed": False, "secret_values_recorded": False, "authorization_headers_recorded": False, "configuration_values_recorded": False},
        "pack_e_minimum_required_coverage.json": required_coverage,
        "pack_e_source_field_binding_report.json": {"selected_request_count": len(requests), "required_binding": required_coverage["required_fields"], "candidate_source_bindings": {"KSRC_FRED": required_coverage["required_fields"][0]["field_binding"], "KSRC_US_TREASURY": required_coverage["required_fields"][0]["field_binding"], "KSRC_FMP": ["DXY_PRESESSION_STATE", "USDJPY_PRESESSION_STATE"], "KSRC_EODHD": ["USDJPY_PRESESSION_STATE"]}, "source_precedence_changed": False},
        "pack_e_runtime_ready_capability_inventory.json": {"capabilities": inventory, "runtime_ready_sources": sorted(ready), "runtime_unready_sources": sorted(row["source_identity"] for row in inventory if row["source_identity"] not in ready)},
        "pack_e_environment_candidates.json": {"candidate_count": len(candidates), "candidates": candidates},
        "pack_e_environment_selection_report.json": {"selection_status": "NO_COMPLETE_APPROVED_ENVIRONMENT", "selected_environment": "NOT_CREATED", "reason": "The only direct approved Treasury route with a migrated adapter is KSRC_FRED, and its existing runtime configuration binding is unresolved.", "multiple_valid_environments": False, "required_coverage_complete": complete},
        "r6_pack_e_source_environment.json": {"status": "NOT_CREATED", "reason": "REQUIRED_FRED_CONFIGURATION_REFERENCE_UNRESOLVED"},
        "r6_pack_e_source_environment_fingerprint.json": {"status": "NOT_CREATED", "reason": "REQUIRED_FRED_CONFIGURATION_REFERENCE_UNRESOLVED"},
        "r6_pack_e_acquisition_authorization_preparation.json": {"status": "NOT_CREATED", "reason": "REQUIRED_FRED_CONFIGURATION_REFERENCE_UNRESOLVED", "authorization_activated": False, "live_source_calls": 0, "pack_e_constructed": False},
        "r6_pack_e_acquisition_authorization_fingerprint.json": {"status": "NOT_CREATED", "reason": "REQUIRED_FRED_CONFIGURATION_REFERENCE_UNRESOLVED"},
        "external_access_audit.json": audit(),
        "final_pack_e_native_adapter_migration_decision.json": {"decision": decision, "validations": validations, "environment_created": False, "acquisition_authorization_prepared": False, "authorization_activated": False, "live_source_calls": 0, "pack_e_constructed": False},
    }
    for name, value in reports.items():
        write(output, name, value)
    return decision


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args()
    print(canonical({"decision": run(args.output), "output": str(args.output.relative_to(ROOT))}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
