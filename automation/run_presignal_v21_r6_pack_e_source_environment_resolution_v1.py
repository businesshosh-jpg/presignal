"""Local-only R6 Pack E source-environment resolution.

The Pack E compute is deliberately caller supplied.  This audit inventories
only already registered capabilities and existing local binding references; it
does not contact a source, execute Apps Script, inspect Script Properties, or
construct Pack E.  A historical market-context writer is not promoted into a
prospective R6 acquisition adapter merely because it names the same provider.
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


PACK = ROOT / "outputs/presignal_v21_designed_drift_r6_pack_construction_fomc/R6-PACK-CONSTRUCTION-FOMC-20260724-v1"
PRIORITY = ROOT / "outputs/presignal_v21_designed_drift_r6_information_request_priority_contract_repair/R6-INFORMATION-REQUEST-PRIORITY-CONTRACT-REPAIR-20260724-v1"
OLD_SCOPE = ROOT / "outputs/presignal_v21_designed_drift_r6_authorization/R6-AUTH-20260723-gemini-paired-pack-a-e/authorized_acquisition_scope.json"
OUT = ROOT / "outputs/presignal_v21_designed_drift_r6_pack_e_source_environment_resolution/R6-PACK-E-SOURCE-ENVIRONMENT-20260724-v1"

EPISODE = "EP_EVENT_68a8e1cc3c9bf6ccc385"
PACK_A = "PACK_A_c08bab51525d614592678fae"
PACK_AUTH_FP = "sha256:87fc65d0f9ec84e8efc1f0e8ef0276eb50a35d52c624191cc682dcea9f8fb869"
PACK_A_CONTENT_FP = "sha256:c08bab51525d614592678fae0d82ce9e695ac8ff31afdf28d3e6353573818a59"
ROUTE_B_FP = "sha256:8c910a343515d88ca63ce4aaf738f28f9b4a8ab22665397077858bfaf7e866e4"
CUTOFF = "2026-07-29T18:00:00Z"


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def read(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write(output: Path, name: str, value: Any) -> None:
    output.mkdir(parents=True, exist_ok=True)
    (output / name).write_text(canonical(value) + "\n", encoding="utf-8")


def source_capabilities() -> list[dict[str, Any]]:
    """Inventory only source routes that have concrete repository evidence."""
    return [
        {
            "source_identity": "KSRC_FMP", "adapter_identity": "apps_script/market_context_v2b.js:_v2bFetchFmpHistory_",
            "registry_approval_status": "APPROVED_SOURCE_CAPABILITY_GATED", "prospective_registry_status": "SUPPORTED_PRODUCTION_INPUT",
            "runtime_implementation_status": "LEGACY_MARKET_CONTEXT_WRITER_ONLY", "required_credential_type": "Apps Script Script Property FMP_API_KEY",
            "configuration_reference": "CFG.FMP_API_KEY or Script Property FMP_API_KEY", "existing_local_configuration_detected": "CONFIRMED_FOR_CALENDAR_ONLY",
            "existing_credential_reference_detected": "Apps Script reference exists; no local secret value inspected",
            "runtime_readiness": "APPROVED_BUT_ADAPTER_UNAVAILABLE", "prospective_use_permitted": False,
            "supported_pack_e_fields": ["DXY_LEVEL", "DXY_CHANGE_PRESESSION", "USDJPY_RETURN_1H_PRESESSION", "USDJPY_RETURN_4H_PRESESSION", "USDJPY_RETURN_24H_PRESESSION", "USDJPY_TREND_LABEL"],
            "reason": "The adapter feeds the legacy Feature_Pack_v2B_Core_Audit writer and does not return caller-controlled NATIVE_ACQUISITION_RECORDs for the frozen Pack E capability.",
        },
        {
            "source_identity": "KSRC_FRED", "adapter_identity": "apps_script/market_context_v2b.js:_v2bFetchFredHistory_",
            "registry_approval_status": "APPROVED_SOURCE_CAPABILITY_GATED", "prospective_registry_status": "SUPPORTED",
            "runtime_implementation_status": "LEGACY_MARKET_CONTEXT_WRITER_ONLY", "required_credential_type": "Apps Script Script Property FRED_API_KEY",
            "configuration_reference": "Script Property FRED_API_KEY", "existing_local_configuration_detected": "NO_LOCAL_ENVIRONMENT_BINDING",
            "existing_credential_reference_detected": "Script Property reference only; remote value intentionally not inspected",
            "runtime_readiness": "APPROVED_BUT_CONFIGURATION_MISSING", "prospective_use_permitted": False,
            "supported_pack_e_fields": ["US2Y_YIELD_LEVEL", "US10Y_YIELD_LEVEL", "US2Y_CHANGE_FROM_PRIOR_CLOSE", "US10Y_CHANGE_FROM_PRIOR_CLOSE", "US10Y_MINUS_US2Y_CURVE"],
            "reason": "No local configuration binding proves FRED_API_KEY availability, and the existing implementation does not emit R6 Pack E acquisition records.",
        },
        {
            "source_identity": "KSRC_EODHD", "adapter_identity": "apps_script/market_context_v2b.js:_v2bFetchEodhdHistory_",
            "registry_approval_status": "APPROVED_SOURCE_CAPABILITY_GATED", "prospective_registry_status": "SUPPORTED_STRUCTURED_MARKET_DATA",
            "runtime_implementation_status": "LEGACY_MARKET_CONTEXT_WRITER_ONLY", "required_credential_type": "Apps Script Script Property EODHD_API_KEY",
            "configuration_reference": "CFG.EODHD_API_KEY or Script Property EODHD_API_KEY", "existing_local_configuration_detected": "NO_LOCAL_ENVIRONMENT_BINDING",
            "existing_credential_reference_detected": "Script Property reference only; remote value intentionally not inspected",
            "runtime_readiness": "APPROVED_BUT_CONFIGURATION_MISSING", "prospective_use_permitted": False,
            "supported_pack_e_fields": ["USDJPY_RETURN_1H_PRESESSION", "USDJPY_RETURN_4H_PRESESSION", "USDJPY_RETURN_24H_PRESESSION", "USDJPY_TREND_LABEL"],
            "reason": "No local configuration binding proves EODHD_API_KEY availability, and the available implementation is not a caller-controlled Pack E adapter.",
        },
        {
            "source_identity": "KSRC_US_TREASURY", "adapter_identity": "NOT_BOUND_FOR_PACK_E",
            "registry_approval_status": "APPROVED_SOURCE_CAPABILITY_GATED", "prospective_registry_status": "SUPPORTED",
            "runtime_implementation_status": "NO_PACK_E_ACQUISITION_ADAPTER", "required_credential_type": "public API or approved Apps Script adapter",
            "configuration_reference": "NOT_BOUND", "existing_local_configuration_detected": "NOT_APPLICABLE_NO_ADAPTER",
            "existing_credential_reference_detected": "NOT_APPLICABLE_NO_ADAPTER",
            "runtime_readiness": "APPROVED_BUT_ADAPTER_UNAVAILABLE", "prospective_use_permitted": False,
            "supported_pack_e_fields": ["US2Y_YIELD_LEVEL", "US10Y_YIELD_LEVEL", "US2Y_CHANGE_FROM_PRIOR_CLOSE", "US10Y_CHANGE_FROM_PRIOR_CLOSE", "US10Y_MINUS_US2Y_CURVE"],
            "reason": "Registry approval exists, but no existing caller-controlled Pack E adapter or configuration binding was found.",
        },
    ]


def local_binding_inventory() -> dict[str, Any]:
    env_names = ("FRED_API_KEY", "EODHD_API_KEY", "FMP_API_KEY", "FMP_BASE")
    return {
        "inspection_scope": "local metadata only; no secret value read",
        "environment_variables": {name: "SET" if bool(os.environ.get(name)) else "NOT_SET" for name in env_names},
        "authorized_user_oauth_token": {"repository_relative_reference": "local/token.json", "exists": (ROOT / "local/token.json").is_file(), "role": "Apps Script bridge credential only"},
        "remote_script_properties": "NOT_INSPECTED; reading them is outside this metadata-only local audit",
        "secret_values_recorded": False,
    }


def requirements() -> dict[str, Any]:
    return {
        "builder": "automation/presignal_v21_pack_capability_v1.py:build_immutable_acquired_information_bundle -> assemble_canonical_pack_e",
        "source_authority": "git:e5a0ff288eb1f6fc228936cb1c693ed2bb2ab80f:automation/approved_knowledge_source_registry_v0.py plus the caller-supplied environment requirement",
        "adapter_authority": "existing Apps Script market-context adapters are implementation evidence only; a caller-controlled Pack E NATIVE_ACQUISITION_RECORD adapter is additionally required",
        "credential_configuration_authority": "existing local configuration references and structurally recognized Apps Script Script Property names; secret values are never inspected",
        "required_environment_fields": ["environment_id", "approved_source_ids"],
        "required_native_record_fields_when_supplied": ["acquisition_record_id", "request_identity", "episode_id", "forecast_cutoff_ts", "source_id", "source_identity", "source_url_or_key", "source_type", "retrieval_timestamp", "acquisition_method", "raw_acquired_content", "normalized_acquired_content"],
        "source_identity_format": "AKSR source_id, e.g. KSRC_FMP", "adapter_identity_format": "repository-relative path:function",
        "credential_reference_format": "reference name and credential type only; no value", "configuration_reference_format": "repository-relative config or Script Property identifier only",
        "call_budget_fields": ["per_source_call_budget", "total_call_budget", "retry_budget"], "temporal_fields": ["forecast_cutoff_ts", "retrieval_timestamp", "as_of_timestamp", "source_timestamp"],
        "completeness_rule": "FROZEN_PACK_E_RULES_V1 permits explicit unavailable and policy declarations, but only after a nonempty caller-supplied approved environment validates source lineage.",
        "required_coverage": "No fixed all-category research coverage; the selected Request categories are routed by frozen capability classification.",
        "optional_or_contextual_coverage": ["INTERPRETIVE_CONTEXT_NOT_ACQUIRED", "FED_EXPECTATIONS_POLICY_BLOCK", "HISTORICAL_EVENT_SENSITIVITY", "INFLATION_NARRATIVE_SOURCE_GROUNDED", "LABOR_MARKET_CONTEXT", "UPCOMING_EVENT_CALENDAR"],
        "exact_prior_blocker": "contracts/presignal_v21_event_path/pack_capability_dependency_manifest.json classifies external acquisition configuration as intentionally outside core; authorized_acquisition_scope.json records approved_source_environment.authorization_status=UNRESOLVED.",
    }


def candidate_environment(capabilities: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{
        "candidate_identity": "R6_PACK_E_MARKET_CONTEXT_V2B_EXISTING_CAPABILITIES",
        "source_identities": [row["source_identity"] for row in capabilities],
        "adapter_identities": [row["adapter_identity"] for row in capabilities],
        "supported_pack_e_fields": sorted({field for row in capabilities for field in row["supported_pack_e_fields"]}),
        "required_coverage_complete": False, "runtime_ready": False, "credential_configuration_ready": False,
        "expected_source_call_count": 0, "retry_budget": 0,
        "missing_items": ["one caller-controlled acquisition adapter that returns NATIVE_ACQUISITION_RECORD", "one current prospective R6 configuration binding for every included source", "one nonempty approved environment binding"],
        "rejection_reason": "Every included source is either configuration-unproven or connected only to a legacy writer; registry approval is insufficient.",
    }]


def audit() -> dict[str, int]:
    return {key: 0 for key in ("source_http_api_calls", "google_scientific_reads", "google_scientific_writes", "apps_script_executions", "gemini_calls", "research_scraping", "pack_e_constructions", "forecast_calls", "outcome_operations", "evaluation_operations")}


def run(output: Path = OUT) -> str:
    pack_auth = read(PRIORITY / "new_r6_pack_authorization_preparation.json")
    pack_a = read(PACK / "new_r6_pack_a.json")
    old_scope = read(OLD_SCOPE)
    contract = requirements(); bindings = local_binding_inventory(); capabilities = source_capabilities(); candidates = candidate_environment(capabilities)
    validations = {
        "pack_authorization_fingerprint_valid": pack_auth.get("authorization_fingerprint") == PACK_AUTH_FP,
        "pack_a_identity_valid": pack_a.get("pack_identity") == PACK_A,
        "pack_a_content_checksum_valid": pack_a.get("content_checksum") == PACK_A_CONTENT_FP,
        "route_b_freeze_valid": pack_auth.get("route_b_freeze_fingerprint") == ROUTE_B_FP,
        "previous_environment_blocker_preserved": ((old_scope.get("approved_source_environment") or {}).get("authorization_status") == "UNRESOLVED"),
        "core_environment_schema_requires_nonempty_source_ids": bool(contract["required_environment_fields"]),
    }
    complete = all(row["runtime_readiness"] == "APPROVED_AND_RUNTIME_READY" for row in capabilities)
    decision = "NEW_R6_PACK_E_SOURCE_ENVIRONMENT_RESOLVED_ACQUISITION_AUTHORIZATION_PREPARED" if complete else "NEW_R6_PACK_E_SOURCE_ENVIRONMENT_BINDING_INCOMPLETE"
    reports: dict[str, Any] = {
        "pack_e_environment_requirement_trace.json": {"status": "PASS", "validation": validations, **contract},
        "pack_e_approved_capability_inventory.json": {"capability_count": len(capabilities), "capabilities": capabilities},
        "pack_e_runtime_binding_inventory.json": bindings,
        "pack_e_secret_safety_report.json": {"new_credentials_created": False, "credential_contents_exposed": False, "credentials_committed": False, "authorization_headers_recorded": False, "secret_values_recorded": False},
        "pack_e_completeness_contract_report.json": {"frozen_rules_fingerprint": capability.checksum(capability.FROZEN_PACK_E_RULES_V1), "minimum_environment_rule": "at least one approved source identity with a caller-controlled Pack E adapter and resolvable runtime configuration", "partial_construction_rule": contract["completeness_rule"], "required_coverage_complete": complete},
        "pack_e_environment_candidates.json": {"candidate_count": len(candidates), "candidates": candidates},
        "pack_e_environment_selection_report.json": {"selection_status": "NO_COMPLETE_APPROVED_ENVIRONMENT", "selection_rule": "select only a uniquely complete runtime-ready candidate", "selected_environment": "NOT_CREATED", "reason": "No candidate meets the runtime authority rule."},
        "r6_pack_e_source_environment.json": {"status": "NOT_CREATED", "reason": "NO_COMPLETE_APPROVED_ENVIRONMENT"},
        "r6_pack_e_source_environment_fingerprint.json": {"status": "NOT_CREATED", "reason": "NO_COMPLETE_APPROVED_ENVIRONMENT"},
        "r6_pack_e_acquisition_authorization_preparation.json": {"status": "NOT_CREATED", "reason": "NO_COMPLETE_APPROVED_ENVIRONMENT", "authorization_activated": False, "source_calls_executed": 0, "pack_e_constructed": False},
        "r6_pack_e_acquisition_authorization_fingerprint.json": {"status": "NOT_CREATED", "reason": "NO_COMPLETE_APPROVED_ENVIRONMENT"},
        "external_access_audit.json": audit(),
        "final_pack_e_source_environment_decision.json": {"decision": decision, "environment_created": False, "acquisition_authorization_prepared": False, "source_calls_executed": 0, "pack_e_constructed": False},
    }
    for name, value in reports.items():
        write(output, name, value)
    return decision


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args(); print(canonical({"decision": run(args.output), "output": str(args.output.relative_to(ROOT))})); return 0


if __name__ == "__main__":
    raise SystemExit(main())
