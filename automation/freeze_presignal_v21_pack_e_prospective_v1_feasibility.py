#!/usr/bin/env python3
"""Freeze the Round 2 feasibility reclassification without live acquisition."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "outputs" / "presignal_v21_full_round_1_forecast_execution"
ARTIFACT_ID = "PPHB-R2-PACK-E-PROSPECTIVE-V1-FEASIBILITY-RECLASSIFICATION-20260804T043000Z"
DEFAULT_OUTPUT_DIR = BASE / ARTIFACT_ID
PROMPT_FINGERPRINT = "sha256:2515e6c09742e58507efe8d9196ba58473c01f2d5bb9e8b5405405088d323a77"
PROTOCOL_FINGERPRINT = "sha256:d417e4c76d3d38d471dbc76cbf361be4a28dac1b615ecccdc8aa18c37262362f"
ENVELOPE_FINGERPRINT = "sha256:3fe721eee816e48a5eca00c50cbcbc397bec6258d60bdfc7857e8169869efdd0"
T_MINUS_15_FINGERPRINT = "sha256:a4200c3e5704ea1ba172967847e71d664f63b75d64c013fe2fbaf78ee0290085"

SOURCES = (
    {
        "field_family": "US_2_YEAR_TREASURY_YIELD",
        "provider": "FRED", "symbol": "DGS2", "adapter": "apps_script/market_context_v2b.js::_v2bFetchFredHistory_",
        "authentication_route": "Apps Script FRED_API_KEY Script Property",
        "response_schema": "fred.series.observations[] {date, value}", "value_unit": "percent",
        "normalized_fields": ["latest_value", "latest_observation_timestamp_utc", "change_24h_basis_points", "change_5d_basis_points", "direction_24h", "direction_5d"],
    },
    {
        "field_family": "US_10_YEAR_TREASURY_YIELD",
        "provider": "FRED", "symbol": "DGS10", "adapter": "apps_script/market_context_v2b.js::_v2bFetchFredHistory_",
        "authentication_route": "Apps Script FRED_API_KEY Script Property",
        "response_schema": "fred.series.observations[] {date, value}", "value_unit": "percent",
        "normalized_fields": ["latest_value", "latest_observation_timestamp_utc", "change_24h_basis_points", "change_5d_basis_points", "direction_24h", "direction_5d"],
    },
    {
        "field_family": "USDJPY_MARKET_STATE",
        "provider": "EODHD", "symbol": "USDJPY.FOREX", "adapter": "apps_script/market_context_v2b.js::_v2bFetchEodhdHistory_",
        "authentication_route": "Apps Script EODHD_API_KEY Script Property via _getEodhdApiKey_",
        "response_schema": "eodhd.eod[] {date, close}", "value_unit": "USDJPY_level_and_pips",
        "normalized_fields": ["latest_value", "latest_observation_timestamp_utc", "change_24h_pips", "change_5d_pips", "direction_24h", "direction_5d"],
    },
    {
        "field_family": "US_DOLLAR_INDEX_MARKET_STATE",
        "provider": "FMP", "symbol": "DX-Y.NYB", "adapter": "apps_script/market_context_v2b.js::_v2bFetchFmpHistory_",
        "authentication_route": "Apps Script FMP_API_KEY Script Property or CFG.FMP_API_KEY",
        "response_schema": "fmp.historical[] {date, close}", "value_unit": "index_points_and_percent",
        "normalized_fields": ["latest_value", "latest_observation_timestamp_utc", "change_24h_percent", "change_5d_percent", "direction_24h", "direction_5d"],
    },
    {
        "field_family": "SP500_MARKET_STATE",
        "provider": "EODHD", "symbol": "GSPC.INDX", "adapter": "apps_script/market_context_v2b.js::_v2bFetchEodhdHistory_",
        "authentication_route": "Apps Script EODHD_API_KEY Script Property via _getEodhdApiKey_",
        "response_schema": "eodhd.eod[] {date, close}", "value_unit": "index_points_and_percent",
        "normalized_fields": ["latest_value", "latest_observation_timestamp_utc", "change_24h_percent", "change_5d_percent", "direction_24h", "direction_5d"],
    },
    {
        "field_family": "GOLD_MARKET_STATE",
        "provider": "EODHD", "symbol": "XAUUSD.FOREX", "adapter": "apps_script/market_context_v2b.js::_v2bFetchEodhdHistory_",
        "authentication_route": "Apps Script EODHD_API_KEY Script Property via _getEodhdApiKey_",
        "response_schema": "eodhd.eod[] {date, close}", "value_unit": "price_and_percent",
        "normalized_fields": ["latest_value", "latest_observation_timestamp_utc", "change_24h_percent", "change_5d_percent", "direction_24h", "direction_5d"],
    },
    {
        "field_family": "WTI_CRUDE_OIL_MARKET_STATE",
        "provider": "FMP", "symbol": "CLUSD", "adapter": "apps_script/market_context_v2b.js::_v2bFetchFmpHistory_",
        "authentication_route": "Apps Script FMP_API_KEY Script Property or CFG.FMP_API_KEY",
        "response_schema": "fmp.historical[] {date, close}", "value_unit": "price_and_percent",
        "normalized_fields": ["latest_value", "latest_observation_timestamp_utc", "change_24h_percent", "change_5d_percent", "direction_24h", "direction_5d"],
    },
)


class FeasibilityError(RuntimeError):
    """The local evidence does not support a required feasibility decision."""


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def local_source_validation() -> list[dict[str, Any]]:
    source = (ROOT / "apps_script" / "market_context_v2b.js").read_text()
    blueprint = (ROOT / "docs" / "Blueprint_v1.4.md").read_text()
    required_tokens = ["_v2bSortRowsAsc_", "_v2bObservationWindow_", "_v2bFetchFredHistory_", "_v2bFetchEodhdHistory_", "_v2bFetchFmpHistory_"]
    if any(token not in source for token in required_tokens):
        raise FeasibilityError("MARKET_CONTEXT_SOURCE_CONTRACT_MISSING")
    if "Validated sources currently in use are FRED" not in blueprint:
        raise FeasibilityError("BLUEPRINT_SOURCE_AUTHORITY_MISSING")
    rows = []
    for item in SOURCES:
        if item["symbol"] not in source:
            raise FeasibilityError("SOURCE_SYMBOL_NOT_IN_ACCEPTED_ADAPTER:" + item["symbol"])
        rows.append({
            **item,
            "classification": "PROSPECTIVE_SOURCE_REQUIRES_IMPLEMENTATION_AUTHORITY",
            "accepted_source_route": True,
            "deterministic_sorting_supported": True,
            "lookback_supported": "previous available observation and fifth prior available observation",
            "zero_write_fetch_helper": True,
            "raw_response_preservation": "REQUIRES_RETURN_ONLY_ADAPTER_IMPLEMENTATION",
            "timestamp_capability": "DATE_ONLY_NORMALIZATION_IN_CURRENT_ADAPTER",
            "blocking_reason": "Current adapter discards provider availability timestamps and has no return-only artifact surface; implementation must preserve raw responses and authoritative UTC availability timestamps.",
        })
    return rows


def timestamp_rules() -> dict[str, Any]:
    return {
        "required_precedence": [
            "authoritative observation timestamp",
            "authoritative publication timestamp when observation time is not availability",
            "retrieval timestamp as operational lineage only, never as availability substitution",
        ],
        "eligibility": "source_available_timestamp_utc < episode_t_minus_15_cutoff_utc",
        "strict_boundary": "equality at cutoff is ineligible; timestamps normalize to UTC; latest eligible observation is selected after explicit ascending sort",
        "rejection_rules": ["post-cutoff observation", "post-cutoff revision", "missing or ambiguous timestamp", "current value backfilled to earlier cutoff"],
        "current_validation": "BLOCKED: _v2bFetchFredHistory_, _v2bFetchEodhdHistory_, and _v2bFetchFmpHistory_ normalize rows to date/value and do not retain an authoritative UTC availability timestamp.",
    }


def stale_missing_rules() -> dict[str, Any]:
    return {
        "allowed_field_statuses": ["AVAILABLE", "STALE", "UNAVAILABLE", "TIMESTAMP_UNRESOLVED", "SOURCE_FAILURE"],
        "completeness_states": {
            "COMPLETE": "all seven source families AVAILABLE",
            "COMPLETE_WITH_GOVERNED_MISSING": "one or more UNAVAILABLE values under a frozen source-calendar rule, without substitution",
            "INCOMPLETE": "source, timestamp, or required-field authority is unresolved",
        },
        "prohibited_missing_substitutions": ["zero", "nearest unrelated series", "AI estimate", "prose", "post-release data"],
        "stale_threshold": "UNRESOLVED_PROTOCOL_PARAMETER: the accepted adapter selects prior available rows but provides no source-calendar stale threshold for FRED, EODHD, or FMP.",
        "direction_threshold": "UNRESOLVED_PROTOCOL_PARAMETER: no accepted per-family flat threshold governs prospective 24h/5d market-state direction labels.",
    }


def return_only_artifact_schema() -> dict[str, Any]:
    return {
        "required_fields": [
            "pack_id", "pack_identity", "contract_id", "contract_fingerprint", "episode_id", "event_snapshot_id",
            "release_timestamp_utc", "forecast_cutoff_utc", "construction_timestamp_utc", "source_mode",
            "field_contract_version", "source_request_inventory", "raw_response_references", "source_schema_bindings",
            "normalized_market_state", "field_statuses", "source_timestamps", "stale_decisions", "missing_decisions",
            "leakage_decision", "completeness_state", "deterministic_serialization_version", "artifact_fingerprint",
        ],
        "fixed_values": {"pack_identity": "PACK_E_PROSPECTIVE_V1", "source_mode": "PROSPECTIVE", "google_writes": 0, "retries": 0},
        "status": "PROPOSED_INACTIVE_RETURN_ONLY_SCHEMA",
    }


def build_evidence() -> dict[str, Any]:
    sources = local_source_validation()
    timestamps = timestamp_rules()
    stale = stale_missing_rules()
    artifact_schema = return_only_artifact_schema()
    amendment = {
        "amendment_id": "PPHB-R2-PROSPECTIVE-FEASIBILITY-PACK-E-V1-AMENDMENT-20260804T043000Z",
        "decisions": ["ROUND_2_CONFIRMATORY_PROTOCOL_CLOSED_PACK_E_NON_EQUIVALENT", "ROUND_2_RECLASSIFIED_AS_PROSPECTIVE_FEASIBILITY"],
        "bindings": {
            "prior_pack_e_study_fingerprint": "sha256:80ebe505eb636467e2dbb86f4358525199c6a7837cb5b3a6cba4fe7e11e1c862",
            "equivalence_sample_fingerprint": "sha256:4cf4abed6c9b5a908bcbac40922407652488797f80a7ae86f4ef4f134d3dceb9",
            "round_2_protocol_fingerprint": PROTOCOL_FINGERPRINT,
            "round_2_envelope_fingerprint": ENVELOPE_FINGERPRINT,
            "t_minus_15_amendment_fingerprint": T_MINUS_15_FINGERPRINT,
        },
        "pack_identity": "PACK_E_PROSPECTIVE_V1",
        "non_equivalence": ["not historical PACK_E", "not an equivalent historical Pack E implementation", "no historical replication claim", "no inference about historical Pack E"],
        "confirmatory_protocol": {"status": "CLOSED_NON_EXECUTABLE", "inactive_targets": ["120 eligible Episodes", "240 common paired-scoreable observations", "200-pair inference minimum"], "existing_dispatch_authorizations_reusable": False},
        "preserved_boundary": {"pack_a": "BASELINE", "primary_endpoint": "T+15 directional accuracy", "strict_secondary": "Immediate Impulse", "fixed_provider_routes": True, "blocked_slice_001_non_reusable": True},
        "feasibility_boundary": "Broader enrollment is prohibited pending one-Episode/one-provider smoke-test success under separately frozen authority.",
    }
    amendment["fingerprint"] = digest({key: value for key, value in amendment.items() if key != "fingerprint"})
    source_authority = {
        "decision": "PACK_E_PROSPECTIVE_V1_SOURCE_AUTHORITY_FROZEN",
        "source_families": sources,
        "scope": "Exact source identities are frozen; return-only acquisition implementation is not authorized.",
    }
    blockers = [
        "authoritative UTC availability timestamp absent from every current normalized source row",
        "source-calendar stale threshold absent",
        "per-family directional flat threshold absent",
    ]
    field_contract = {
        "decision": "PACK_E_PROSPECTIVE_V1_FIELD_CONTRACT_BLOCKED",
        "pack_identity": "PACK_E_PROSPECTIVE_V1",
        "closed_source_family_count": len(SOURCES),
        "source_family_names": [row["field_family"] for row in SOURCES],
        "reason": "The seven-source family inventory is fixed, but strict timestamp, stale, and directional-normalization rules cannot be completed from accepted local evidence.",
        "blockers": blockers,
        "historical_equivalence_claim": False,
    }
    lead_time = {
        "decision": "PACK_E_PROSPECTIVE_V1_LEAD_TIME_BLOCKED",
        "formula": "admission_deadline = T_minus_15_cutoff - maximum_prerequisite_execution_window - safety_margin",
        "reason": "No accepted per-source transport timeout or bounded return-only adapter duration exists; therefore neither the maximum window nor smallest defensible safety margin can be derived.",
    }
    prompt = {
        "decision": "PACK_E_PROSPECTIVE_V1_PROMPT_COMPATIBILITY_CONFIRMED",
        "prompt_fingerprint": PROMPT_FINGERPRINT,
        "evidence": "The frozen arm_context binds FULL_CONTEXT through information_pack and information_pack_fingerprint; the prospective Pack can populate that existing container without prompt text changes.",
        "limitations": "Compatibility does not cure timestamp, stale, direction-threshold, or lead-time blockers.",
    }
    ceilings = {
        "per_episode": {"FRED": 2, "EODHD": 3, "FMP": 2, "total_source_calls": 7, "google_writes": 0, "provider_forecast_calls": 0, "outcome_calls": 0, "retries": 0},
        "per_existing_48_episode_slice_upper_bound": {"FRED": 96, "EODHD": 144, "FMP": 96, "total_source_calls": 336},
        "status": "IMPLEMENTATION_INPUT_ONLY_NOT_ACTIVE_AUTHORITY",
    }
    implementation = {
        "package_id": "PPHB-R2-PACK-E-PROSPECTIVE-V1-IMPLEMENTATION-AUTHORIZATION-INPUTS-20260804T043000Z",
        "status": "PACK_E_PROSPECTIVE_V1_IMPLEMENTATION_REMAINS_BLOCKED",
        "scope": "return-only local adapter only; raw preservation, deterministic normalization, strict timestamp enforcement, safe resume, duplicate prevention, and immutable artifact generation",
        "source_families": [{"provider": row["provider"], "symbol": row["symbol"]} for row in SOURCES],
        "ceilings": ceilings,
        "blocked_by": blockers + [lead_time["reason"]],
        "prohibitions": ["source calls", "Google writes", "provider forecasts", "Outcome activity", "evaluation", "adapter deployment"],
    }
    implementation["fingerprint"] = digest({key: value for key, value in implementation.items() if key != "fingerprint"})
    result = {
        "artifact_id": ARTIFACT_ID,
        "schema_version": "1.0.0",
        "recorded_utc": "2026-08-04T04:30:00Z",
        "amendment": amendment,
        "source_authority": source_authority,
        "field_contract": field_contract,
        "timestamp_rules": timestamps,
        "stale_missing_rules": stale,
        "execution_ceilings": ceilings,
        "lead_time": lead_time,
        "return_only_artifact_schema": artifact_schema,
        "prompt_compatibility": prompt,
        "implementation_authorization_inputs": implementation,
        "activity": {"provider_calls": 0, "google_access": 0, "google_writes": 0, "market_data_calls": 0, "outcome_activity": 0, "evaluation_activity": 0, "retries": 0},
    }
    result["fingerprint"] = digest({key: value for key, value in result.items() if key != "fingerprint"})
    return result


def freeze(output_dir: Path = DEFAULT_OUTPUT_DIR) -> dict[str, Any]:
    if output_dir.exists():
        raise FeasibilityError("PACK_E_PROSPECTIVE_V1_FEASIBILITY_ARTIFACT_ALREADY_EXISTS")
    result = build_evidence()
    output_dir.mkdir(parents=True)
    files = {
        "round_2_feasibility_protocol_amendment.json": result["amendment"],
        "source_feasibility_matrix.json": result["source_authority"],
        "field_contract_blocker.json": result["field_contract"],
        "timestamp_rules.json": result["timestamp_rules"],
        "stale_missing_rules.json": result["stale_missing_rules"],
        "execution_ceilings.json": result["execution_ceilings"],
        "lead_time_analysis.json": result["lead_time"],
        "return_only_artifact_schema.json": result["return_only_artifact_schema"],
        "prompt_compatibility.json": result["prompt_compatibility"],
        "implementation_authorization_inputs.json": result["implementation_authorization_inputs"],
        "validation_results.json": {"passed": True, "activity": result["activity"], "no_historical_pack_e_equivalence_claim": True},
        "feasibility_reclassification_report.json": result,
    }
    for name, value in files.items():
        (output_dir / name).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()
    print(json.dumps(freeze(args.output_dir), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
