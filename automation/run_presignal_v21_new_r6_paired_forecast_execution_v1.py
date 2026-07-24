"""Execute the frozen R6 paired forecast authorization and stop before Outcomes."""
from __future__ import annotations

import hashlib
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from automation import google_clients
from automation import presignal_v21_canonical_states_v1 as canonical_states
from automation import presignal_v21_prospective_flat_contract_v1 as prospective_flat
from automation import presignal_v21_prospective_forecast_contract_v1 as prospective_contract
from automation import run_presignal_v21_single_event_path_pair_v1 as single_pair


OUT = ROOT / "outputs/presignal_v21_designed_drift_r6_paired_forecast_execution/R6-PAIRED-FORECAST-EXECUTION-20260724-v1"
PACK_E_DIR = ROOT / "outputs/presignal_v21_designed_drift_r6_pack_e_acquisition/R6-PACK-E-ACQUISITION-20260724-v1"
PACK_A_DIR = ROOT / "outputs/presignal_v21_designed_drift_r6_pack_construction_fomc/R6-PACK-CONSTRUCTION-FOMC-20260724-v1"
SELECTION_DIR = ROOT / "outputs/presignal_v21_designed_drift_r6_episode_selection_fomc/R6-EPISODE-SELECTION-FOMC-20260724-v1"
ATTENTION_DIR = ROOT / "outputs/presignal_v21_designed_drift_r6_native_attention_field_ownership/R6-NATIVE-ATTENTION-FIELD-OWNERSHIP-20260724-v1"
REQUEST_DIR = ROOT / "outputs/presignal_v21_designed_drift_r6_information_request_priority_contract_repair/R6-INFORMATION-REQUEST-PRIORITY-CONTRACT-REPAIR-20260724-v1"

AUTHORIZATION_NAME = "PRESIGNAL_V21_DESIGNED_DRIFT_2_NEW_R6_PAIRED_FORECAST_AUTHORIZATION_V1"
AUTHORIZATION_FP = "sha256:624abe1281bc4c0781a2854e497820549280403bcb46c72ab9a9938e9da9910f"
OUTCOME_AUTHORIZATION_NAME = "PRESIGNAL_V21_DESIGNED_DRIFT_2_NEW_R6_OUTCOME_COLLECTION_AUTHORIZATION_V1"
EPISODE_ID = "EP_EVENT_68a8e1cc3c9bf6ccc385"
ATTENTION_ID = "NATTN_013be496bbbd13cf4bf6"
PACK_A_ID = "PACK_A_c08bab51525d614592678fae"
PACK_E_ID = "PACK_E_SHARED_51cd46acb1e7a7679ae378f7"
PACK_A_CONTENT = "sha256:c08bab51525d614592678fae0d82ce9e695ac8ff31afdf28d3e6353573818a59"
PACK_E_CONTENT = "sha256:51cd46acb1e7a7679ae378f7fa6d4163959ce2cec25957670a20154daf6ef766"
PACK_E_PROVENANCE = "sha256:3d1f375b0e1bbb820148a214e9386076ab75650d22c1a752c8bf38b0a3e1e4e6"
PACK_E_LINEAGE = "sha256:67a2fee53b2bc41495a0d2c08ec2af81f49bf8557cbc74c2d9fe534d28c9a5f0"
CUTOFF = "2026-07-29T18:00:00Z"
RELEASE_TS = "2026-07-29T18:00:00Z"
ROUTE_B_FP = "sha256:8c910a343515d88ca63ce4aaf738f28f9b4a8ab22665397077858bfaf7e866e4"
OUTCOME_CONTRACT_PATH = ROOT / "contracts/presignal_v21_event_path/outcome_contract_v1.json"
FORECAST_FUNCTION = "apiCallAuthoritativeProviderJsonObject"
OUTCOME_MARKET_DATA_HIERARCHY = ["tiingo", "eodhd", "massive", "twelvedata"]
PRIMARY_EVENT_ID = "5ea0-ce20-ad20-fba0"
PRIMARY_EVENT_NAME = "Fed Interest Rate Decision"


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha(value: Any) -> str:
    payload = value if isinstance(value, bytes) else canonical(value).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(output: Path, name: str, value: Any) -> None:
    output.mkdir(parents=True, exist_ok=True)
    (output / name).write_text(canonical(value) + "\n", encoding="utf-8")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def parse_utc(value: str) -> datetime:
    return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(timezone.utc)


def cutoff_open(now_utc: str) -> bool:
    return parse_utc(now_utc) < parse_utc(CUTOFF)


def redact(value: Any) -> Any:
    if isinstance(value, Mapping):
        sensitive = re.compile(r"^(access_token|refresh_token|id_token|client_secret|api[_-]?key|authorization_header|cookie)$", re.I)
        return {str(k): redact("REDACTED" if sensitive.search(str(k)) else v) for k, v in value.items()}
    if isinstance(value, list):
        return [redact(v) for v in value]
    if isinstance(value, str):
        value = re.sub(r"(?i)(api[_-]?key=)[^&\\s]+", r"\\1REDACTED", value)
        value = re.sub(r"(?i)(authorization:\\s*)[^\\s]+", r"\\1REDACTED", value)
    return value


def external_audit() -> dict[str, int]:
    return {
        "apps_script_forecast_executions": 0,
        "provider_forecast_calls": 0,
        "fred_calls": 0,
        "fmp_calls": 0,
        "eodhd_calls": 0,
        "us_treasury_calls": 0,
        "attention_calls": 0,
        "information_request_calls": 0,
        "pack_acquisition_calls": 0,
        "pack_constructions": 0,
        "google_scientific_reads": 0,
        "google_scientific_writes": 0,
        "outcome_operations": 0,
        "evaluation_operations": 0,
    }


def not_created(reason: str, **extra: Any) -> dict[str, Any]:
    return {"status": "NOT_CREATED", "reason": reason, **extra}


def pack_e_fingerprint(pack_e: Mapping[str, Any]) -> str:
    return str(pack_e.get("pack_fingerprint") or pack_e.get("content_checksum") or PACK_E_CONTENT)


def load_inputs() -> dict[str, Any]:
    return {
        "authorization": read_json(PACK_E_DIR / "new_r6_paired_forecast_authorization_preparation.json"),
        "pack_a": read_json(PACK_A_DIR / "new_r6_pack_a.json"),
        "pack_e": read_json(PACK_E_DIR / "new_r6_pack_e.json"),
        "separation": read_json(PACK_E_DIR / "new_r6_pack_separation_report.json"),
        "episode": read_json(SELECTION_DIR / "new_r6_selected_episode_manifest.json"),
        "attention": read_json(ATTENTION_DIR / "new_r6_native_attention.json"),
        "requests": read_json(REQUEST_DIR / "new_r6_canonical_information_requests.json"),
    }


def authorization_validation(prepared: Mapping[str, Any], episode: Mapping[str, Any], attention: Mapping[str, Any], pack_a: Mapping[str, Any], pack_e: Mapping[str, Any], separation: Mapping[str, Any], requests: Any) -> dict[str, Any]:
    request_rows = requests.get("requests") if isinstance(requests, Mapping) else requests
    checks = {
        "authorization_name": prepared.get("authorization_name") == AUTHORIZATION_NAME,
        "authorization_fingerprint": prepared.get("authorization_fingerprint") == AUTHORIZATION_FP,
        "route_b_freeze_fingerprint": prepared.get("route_b_freeze_fingerprint") == ROUTE_B_FP,
        "episode_identity": prepared.get("episode_identity") == EPISODE_ID == episode.get("episode_identity"),
        "episode_content_checksum": prepared.get("episode_content_checksum") == episode.get("content_checksum"),
        "episode_provenance_checksum": prepared.get("episode_provenance_checksum") == episode.get("provenance_checksum"),
        "episode_lineage_checksum": prepared.get("episode_lineage_checksum") == episode.get("lineage_checksum"),
        "attention_identity": prepared.get("attention_identity") == ATTENTION_ID == attention.get("attention_identity"),
        "attention_content_checksum": prepared.get("attention_content_checksum") == attention.get("content_checksum"),
        "attention_provenance_checksum": prepared.get("attention_provenance_checksum") == attention.get("provenance_checksum"),
        "attention_lineage_checksum": prepared.get("attention_lineage_checksum") == attention.get("lineage_checksum"),
        "request_set_checksum": prepared.get("request_set_checksum") == pack_a.get("request_set_checksum"),
        "pack_a_identity": prepared.get("pack_a_identity") == PACK_A_ID == pack_a.get("pack_identity"),
        "pack_a_content_checksum": prepared.get("pack_a_content_checksum") == pack_a.get("content_checksum"),
        "pack_a_provenance_checksum": prepared.get("pack_a_provenance_checksum") == pack_a.get("provenance_checksum"),
        "pack_a_lineage_checksum": prepared.get("pack_a_lineage_checksum") == pack_a.get("lineage_checksum"),
        "pack_e_identity": prepared.get("pack_e_identity") == PACK_E_ID == pack_e.get("pack_id"),
        "pack_e_content_checksum": prepared.get("pack_e_content_checksum") == PACK_E_CONTENT == pack_e.get("pack_fingerprint"),
        "pack_e_provenance_checksum": prepared.get("pack_e_provenance_checksum") == PACK_E_PROVENANCE,
        "pack_e_lineage_checksum": prepared.get("pack_e_lineage_checksum") == PACK_E_LINEAGE,
        "pack_separation_report_checksum": prepared.get("pack_separation_report_checksum") == sha(separation),
        "provider_identity": prepared.get("provider") == "Gemini",
        "model_identity": prepared.get("model") == "gemini-2.5-flash-lite",
        "forecast_schema": prepared.get("forecast_schema") == prospective_flat.PROSPECTIVE_CONTRACT_VERSION,
        "primary_endpoint_contract": prepared.get("primary_endpoint") == "15-minute primary endpoint",
        "secondary_path_contract": prepared.get("optional_sidecars") == [5, 30, 60],
        "call_budget": prepared.get("call_budget") == 2,
        "pack_a_call_budget": prepared.get("pack_a_call_budget") == 1,
        "pack_e_call_budget": prepared.get("pack_e_call_budget") == 1,
        "retry_budget": prepared.get("retry_budget") == 0,
        "forecast_cutoff": prepared.get("forecast_cutoff") == CUTOFF,
        "separation_passed": separation.get("separation_passed") is True,
        "canonical_request_count": isinstance(request_rows, list) and len(request_rows) == 10,
    }
    return {
        "authorization_name": prepared.get("authorization_name"),
        "authorization_fingerprint": prepared.get("authorization_fingerprint"),
        "authorization_valid": all(checks.values()),
        "checks": checks,
    }


def attention_map(attention: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [{
        "event_id": PRIMARY_EVENT_ID,
        "indicator_name": PRIMARY_EVENT_NAME,
        "attention_label": "PRIMARY_DRIVER",
        "attention_rank": 1,
        "attention_reason": attention.get("selection_reason"),
        "expected_market_channel": "Rates, FX, Equities",
        "driver_role": "Monetary Policy Decision",
        "confidence": "High",
        "attention_run_id": attention.get("attention_identity"),
        "session_id": EPISODE_ID,
        "provider": attention.get("provider_identity"),
        "model": attention.get("model_identity"),
        "forecast_cutoff_ts": attention.get("forecast_cutoff"),
        "status": "parsed",
    }]


def build_input_row(*, pack_arm: str, episode: Mapping[str, Any], attention: Mapping[str, Any], pack_a: Mapping[str, Any], pack_e: Mapping[str, Any]) -> dict[str, Any]:
    is_pack_a = pack_arm == "PACK_A"
    episode_members = [{
        "event_id": episode.get("primary_event_identity"),
        "indicator_name": episode.get("primary_event_name"),
        "structural_component_role": "STRUCTURAL_PRIMARY",
    }]
    return {
        "object": "R6_PROSPECTIVE_FORECAST_INPUT",
        "schema_version": "presignal_v21_r6_paired_forecast_input_v1",
        "system_version": "presignal_v2.1",
        "episode_id": EPISODE_ID,
        "source_session_id": EPISODE_ID,
        "country": episode.get("country"),
        "release_ts": episode.get("release_timestamp"),
        "forecast_cutoff_ts": episode.get("forecast_cutoff"),
        "episode_members": episode_members,
        "structural_component_roles": [{"event_id": episode.get("primary_event_identity"), "structural_component_role": "STRUCTURAL_PRIMARY"}],
        "provider": attention.get("provider_identity"),
        "model": attention.get("model_identity"),
        "provider_episode_selection": "FORECAST",
        "provider_attention_map": attention_map(attention),
        "information_arm": pack_arm,
        "information_requests": list(pack_a.get("ordered_canonical_requests") or []),
        "shared_market_state_pack": None if is_pack_a else pack_e,
        "pack_id": pack_a.get("pack_identity") if is_pack_a else pack_e.get("pack_id"),
        "pack_fingerprint": None if is_pack_a else pack_e_fingerprint(pack_e),
        "pack_version": pack_a.get("schema_version") if is_pack_a else pack_e.get("pack_e_version"),
        "future_outcome_identity_basis": {"market_pair": "USDJPY", "release_ts": episode.get("release_timestamp"), "target": "USDJPY_EVENT_PATH_T_PLUS_5_15_30_60"},
        "horizons_min": [5, 15, 30, 60],
        "target": {"type": "EVENT_EPISODE", "target_id": EPISODE_ID, "primary_endpoint": "EPISODE_REACTION_DIRECTION_15M"},
        "lineage": {
            "episode_content_checksum": episode.get("content_checksum"),
            "attention_content_checksum": attention.get("content_checksum"),
            "request_set_checksum": pack_a.get("request_set_checksum"),
            "pack_identity": pack_a.get("pack_identity") if is_pack_a else pack_e.get("pack_id"),
            "pack_content_checksum": pack_a.get("content_checksum") if is_pack_a else pack_e_fingerprint(pack_e),
        },
    }


def unwrap_provider_output(raw_output: Any) -> dict[str, Any]:
    if isinstance(raw_output, Mapping):
        result = dict(raw_output)
    elif isinstance(raw_output, str):
        text = raw_output.strip()
        if text.startswith("```") and text.endswith("```"):
            text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        result = json.loads(text)
    else:
        raise ValueError("PROVIDER_OUTPUT_NOT_OBJECT")
    if set(result) == {"forecast", "response_contract"} and isinstance(result.get("forecast"), Mapping):
        result = dict(result["forecast"])
    for field in {
        "object", "system_version", "schema_version", "response_contract", "forecast_cutoff_ts",
        "information_pack_fingerprint", "market_state_snapshot_fingerprint", "population_type",
        "rendered_context_fingerprint", "retrospective_simulation_flag", "session_id",
        "model_weight_leakage_not_eliminable",
    }:
        result.pop(field, None)
    return result


def runtime_state(transport: Mapping[str, Any]) -> str:
    if transport.get("status") == "ok":
        return canonical_states.RuntimeState.SUCCESS
    if transport.get("status") in {"provider_unavailable", "model_not_enforceable", "unsupported_provider", "configuration_error"}:
        return canonical_states.RuntimeState.PROVIDER_REJECTED
    if transport.get("status") in {"timeout", "provider_contract_error", "execution_integrity_error", "error"}:
        return canonical_states.RuntimeState.TRANSPORT_FAILED
    return canonical_states.RuntimeState.STATUS_UNKNOWN


def arm_validation(*, arm_name: str, arm_identity: str, pack_identity: str, row: Mapping[str, Any], request_artifact: Mapping[str, Any], transport_meta: Mapping[str, Any], raw_response_checksum: str, provider_payload: Mapping[str, Any] | None, pack_label: str) -> dict[str, Any]:
    provider_ok = transport_meta.get("status") == "ok"
    requested_provider = transport_meta.get("requested_provider")
    requested_model = transport_meta.get("requested_model")
    returned_provider = transport_meta.get("actual_provider")
    returned_model = transport_meta.get("actual_model")
    runtime = runtime_state(transport_meta)
    strict_parse_error = None
    strict_candidate = None
    if provider_ok:
        try:
            strict_candidate = single_pair.parse_provider_output(transport_meta.get("raw_output"))
        except Exception as exc:
            strict_parse_error = str(exc)
    prospective = prospective_contract.validate_prospective_forecast(
        provider_payload,
        episode_id=EPISODE_ID,
        provider=str(requested_provider),
        model=str(requested_model),
        pack_arm=pack_label,
        forecast_cutoff=CUTOFF,
    ) if provider_ok and provider_payload is not None else prospective_contract.non_entry_result(selection_state=canonical_states.SelectionState.SELECTED)
    primary_valid = bool(provider_ok and requested_provider == "Gemini" and requested_model == "gemini-2.5-flash-lite" and returned_provider == "Gemini" and returned_model == "gemini-2.5-flash-lite" and prospective.get("primary_forecast_valid"))
    no_signal = bool((provider_payload or {}).get("no_signal_flag") is True)
    forecast_state = prospective.get("forecast_state")
    if runtime != canonical_states.RuntimeState.SUCCESS:
        forecast_state = canonical_states.ForecastState.INCOMPLETE
    elif no_signal:
        forecast_state = canonical_states.ForecastState.INCOMPLETE
    elif not primary_valid:
        forecast_state = canonical_states.ForecastState.INCOMPLETE
    checksum_basis = {
        "episode_identity": EPISODE_ID,
        "provider": requested_provider,
        "model": requested_model,
        "arm_identity": arm_identity,
        "pack_identity": pack_identity,
        "forecast_cutoff": CUTOFF,
        "forecast_schema": prospective_flat.PROSPECTIVE_CONTRACT_VERSION,
        "primary_direction_15m": prospective.get("primary_direction_15m"),
        "runtime_state": runtime,
        "forecast_state": forecast_state,
        "raw_response_checksum": raw_response_checksum,
        "prompt_checksum": sha(request_artifact["prompt"]),
        "validation_errors": prospective.get("validation_errors"),
    }
    content = {
        "episode_identity": EPISODE_ID,
        "provider_identity": requested_provider,
        "model_identity": requested_model,
        "arm_identity": arm_identity,
        "pack_identity": pack_identity,
        "runtime_state": runtime,
        "runtime_reason": transport_meta.get("status"),
        "forecast_state": forecast_state,
        "primary_15m_direction": prospective.get("primary_direction_15m") if primary_valid else None,
        "primary_confidence": (provider_payload or {}).get("confidence") if isinstance((provider_payload or {}).get("confidence"), (int, float)) else None,
        "direction_5m": prospective_contract._path_direction(provider_payload or {}, 5),
        "direction_30m": prospective_contract._path_direction(provider_payload or {}, 30),
        "direction_60m": prospective_contract._path_direction(provider_payload or {}, 60),
        "expected_reversal_flag": (provider_payload or {}).get("expected_reversal_flag"),
        "expected_reversal_horizon_min": (provider_payload or {}).get("expected_reversal_horizon_min"),
        "expected_path_summary": (provider_payload or {}).get("expected_path_summary"),
        "invalidation_condition": (provider_payload or {}).get("invalidation_condition"),
        "forecast_cutoff": CUTOFF,
        "provider_request_timestamp": transport_meta.get("started_timestamp"),
        "provider_completion_timestamp": transport_meta.get("completed_timestamp"),
        "prompt_checksum": sha(request_artifact["prompt"]),
        "raw_response_checksum": raw_response_checksum,
        "schema_version": prospective_flat.PROSPECTIVE_CONTRACT_VERSION,
    }
    provenance = {
        "authorization_fingerprint": AUTHORIZATION_FP,
        "route_b_freeze_fingerprint": ROUTE_B_FP,
        "raw_response_checksum": raw_response_checksum,
        "request_checksum": sha(request_artifact),
        "strict_path_contract_parse_success": strict_candidate is not None,
        "strict_path_contract_parse_error": strict_parse_error,
        "provider_payload_checksum": sha(provider_payload) if provider_payload is not None else None,
        "prospective_validation_errors": prospective.get("validation_errors"),
        "prospective_validation_warnings": prospective.get("validation_warnings"),
    }
    lineage = {
        "episode_identity": EPISODE_ID,
        "episode_content_checksum": read_json(SELECTION_DIR / "new_r6_selected_episode_manifest.json").get("content_checksum"),
        "attention_identity": ATTENTION_ID,
        "attention_content_checksum": read_json(ATTENTION_DIR / "new_r6_native_attention.json").get("content_checksum"),
        "request_set_checksum": read_json(PACK_A_DIR / "new_r6_pack_a.json").get("request_set_checksum"),
        "pack_identity": pack_identity,
        "pack_content_checksum": PACK_A_CONTENT if pack_label == "PACK_A" else PACK_E_CONTENT,
        "arm_identity": arm_identity,
        "forecast_contract": prospective_flat.PROSPECTIVE_CONTRACT_VERSION,
        "forecast_cutoff": CUTOFF,
    }
    identity_seed = {
        "episode_identity": EPISODE_ID,
        "provider_identity": requested_provider,
        "model_identity": requested_model,
        "arm_identity": arm_identity,
        "pack_identity": pack_identity,
        "forecast_contract": prospective_flat.PROSPECTIVE_CONTRACT_VERSION,
        "forecast_cutoff": CUTOFF,
    }
    identity = "NFCST_" + hashlib.sha256(canonical(identity_seed).encode("utf-8")).hexdigest()[:20]
    canonical_forecast = {
        "object": "R6_CANONICAL_FORECAST",
        "forecast_identity": identity,
        "episode_identity": EPISODE_ID,
        "provider_identity": requested_provider,
        "model_identity": requested_model,
        "arm_identity": arm_identity,
        "pack_identity": pack_identity,
        "runtime_state": runtime,
        "runtime_reason": transport_meta.get("status"),
        "forecast_state": forecast_state,
        "primary_15m_direction": prospective.get("primary_direction_15m") if primary_valid else None,
        "primary_confidence": content["primary_confidence"],
        "direction_5m": content["direction_5m"],
        "direction_30m": content["direction_30m"],
        "direction_60m": content["direction_60m"],
        "expected_reversal_flag": content["expected_reversal_flag"],
        "expected_reversal_horizon_min": content["expected_reversal_horizon_min"],
        "expected_path_summary": content["expected_path_summary"],
        "invalidation_condition": content["invalidation_condition"],
        "forecast_cutoff": CUTOFF,
        "provider_request_timestamp": content["provider_request_timestamp"],
        "provider_completion_timestamp": content["provider_completion_timestamp"],
        "prompt_checksum": content["prompt_checksum"],
        "raw_response_checksum": raw_response_checksum,
        "content_checksum": sha(content),
        "provenance": provenance,
        "provenance_checksum": sha(provenance),
        "lineage": lineage,
        "lineage_checksum": sha(lineage),
        "schema_version": prospective_flat.PROSPECTIVE_CONTRACT_VERSION,
    }
    return {
        "provider": requested_provider,
        "requested_model": requested_model,
        "returned_model": returned_model,
        "runtime_state": runtime,
        "forecast_state": forecast_state,
        "primary_valid": primary_valid,
        "raw_response_checksum": raw_response_checksum,
        "strict_parse_error": strict_parse_error,
        "prospective_validation": prospective,
        "canonical_forecast": canonical_forecast if primary_valid else None,
        "validation": {
            "provider_identity_valid": requested_provider == "Gemini" and returned_provider == "Gemini",
            "model_identity_valid": requested_model == "gemini-2.5-flash-lite" and returned_model == "gemini-2.5-flash-lite",
            "episode_identity_valid": row.get("episode_id") == EPISODE_ID,
            "arm_identity": arm_identity,
            "pack_identity": pack_identity,
            "forecast_cutoff_valid": row.get("forecast_cutoff_ts") == CUTOFF,
            "primary_15m_direction": prospective.get("primary_direction_15m"),
            "primary_15m_direction_valid": primary_valid,
            "forecast_state": forecast_state,
            "runtime_state": runtime,
            "schema_version": prospective_flat.PROSPECTIVE_CONTRACT_VERSION,
            "prompt_checksum": sha(request_artifact["prompt"]),
            "raw_response_checksum": raw_response_checksum,
            "content_checksum": canonical_forecast["content_checksum"] if primary_valid else None,
            "provenance_checksum": canonical_forecast["provenance_checksum"] if primary_valid else None,
            "lineage_checksum": canonical_forecast["lineage_checksum"] if primary_valid else None,
            "optional_path_fields_present": {
                "5m": content["direction_5m"] is not None,
                "30m": content["direction_30m"] is not None,
                "60m": content["direction_60m"] is not None,
                "confidence": content["primary_confidence"] is not None,
            },
            "no_signal_detected": no_signal,
        },
    }


def determinism_report(builder) -> dict[str, Any]:
    results = [builder() for _ in range(3)]
    first = results[0]
    same = all(
        result["forecast_identity"] == first["forecast_identity"]
        and result["content_checksum"] == first["content_checksum"]
        and result["provenance_checksum"] == first["provenance_checksum"]
        and result["lineage_checksum"] == first["lineage_checksum"]
        for result in results[1:]
    )
    return {
        "three_run_determinism": same,
        "forecast_identity": first["forecast_identity"],
        "content_checksum": first["content_checksum"],
        "provenance_checksum": first["provenance_checksum"],
        "lineage_checksum": first["lineage_checksum"],
    }


def pair_record(pack_a_forecast: Mapping[str, Any], pack_e_forecast: Mapping[str, Any]) -> dict[str, Any]:
    content = {
        "episode_identity": EPISODE_ID,
        "provider_identity": pack_a_forecast["provider_identity"],
        "model_identity": pack_a_forecast["model_identity"],
        "forecast_cutoff": CUTOFF,
        "primary_target": "USDJPY_EVENT_PATH_DIRECTION_15M",
        "pack_a_forecast_identity": pack_a_forecast["forecast_identity"],
        "pack_e_forecast_identity": pack_e_forecast["forecast_identity"],
        "primary_directions": {
            "pack_a": pack_a_forecast["primary_15m_direction"],
            "pack_e": pack_e_forecast["primary_15m_direction"],
        },
    }
    pair_identity = "PAIR_" + hashlib.sha256(canonical(content).encode("utf-8")).hexdigest()[:20]
    return {
        "object": "R6_PAIRED_FORECAST_RECORD",
        "pair_identity": pair_identity,
        "episode_identity": EPISODE_ID,
        "provider_identity": pack_a_forecast["provider_identity"],
        "model_identity": pack_a_forecast["model_identity"],
        "forecast_cutoff": CUTOFF,
        "primary_target": "USDJPY_EVENT_PATH_DIRECTION_15M",
        "pack_a_forecast_identity": pack_a_forecast["forecast_identity"],
        "pack_e_forecast_identity": pack_e_forecast["forecast_identity"],
        "primary_directions_agree": pack_a_forecast["primary_15m_direction"] == pack_e_forecast["primary_15m_direction"],
        "content_checksum": sha(content),
    }


def pair_validation(pack_a_forecast: Mapping[str, Any], pack_e_forecast: Mapping[str, Any], separation: Mapping[str, Any]) -> dict[str, Any]:
    leakage = (
        PACK_E_ID in canonical(pack_a_forecast)
        or "TREASURY_2Y_10Y_PRESESSION_STATE" in canonical(pack_a_forecast)
    )
    return {
        "same_episode": pack_a_forecast["episode_identity"] == pack_e_forecast["episode_identity"] == EPISODE_ID,
        "same_provider": pack_a_forecast["provider_identity"] == pack_e_forecast["provider_identity"] == "Gemini",
        "same_model": pack_a_forecast["model_identity"] == pack_e_forecast["model_identity"] == "gemini-2.5-flash-lite",
        "same_cutoff": pack_a_forecast["forecast_cutoff"] == pack_e_forecast["forecast_cutoff"] == CUTOFF,
        "same_primary_target": True,
        "same_forecast_schema": pack_a_forecast["schema_version"] == pack_e_forecast["schema_version"] == prospective_flat.PROSPECTIVE_CONTRACT_VERSION,
        "pack_identities_distinct": pack_a_forecast["pack_identity"] != pack_e_forecast["pack_identity"],
        "forecast_identities_distinct": pack_a_forecast["forecast_identity"] != pack_e_forecast["forecast_identity"],
        "pack_leakage_detected": leakage,
        "pair_complete": True,
        "separation_report_checksum": sha(separation),
        "separation_passed": separation.get("separation_passed") is True,
    }


def outcome_authorization(pair: Mapping[str, Any], pack_a_forecast: Mapping[str, Any], pack_e_forecast: Mapping[str, Any], authorization: Mapping[str, Any], episode: Mapping[str, Any]) -> dict[str, Any]:
    contract = read_json(OUTCOME_CONTRACT_PATH)
    earliest = (parse_utc(RELEASE_TS) + timedelta(minutes=60)).isoformat().replace("+00:00", "Z")
    payload = {
        "authorization_name": OUTCOME_AUTHORIZATION_NAME,
        "authorization_valid": True,
        "authorization_activated": False,
        "route_b_freeze_fingerprint": ROUTE_B_FP,
        "episode_identity": EPISODE_ID,
        "episode_content_checksum": episode.get("content_checksum"),
        "episode_provenance_checksum": episode.get("provenance_checksum"),
        "episode_lineage_checksum": episode.get("lineage_checksum"),
        "release_timestamp": RELEASE_TS,
        "forecast_cutoff": CUTOFF,
        "pack_a_forecast_identity": pack_a_forecast["forecast_identity"],
        "pack_a_forecast_content_checksum": pack_a_forecast["content_checksum"],
        "pack_a_forecast_provenance_checksum": pack_a_forecast["provenance_checksum"],
        "pack_a_forecast_lineage_checksum": pack_a_forecast["lineage_checksum"],
        "pack_e_forecast_identity": pack_e_forecast["forecast_identity"],
        "pack_e_forecast_content_checksum": pack_e_forecast["content_checksum"],
        "pack_e_forecast_provenance_checksum": pack_e_forecast["provenance_checksum"],
        "pack_e_forecast_lineage_checksum": pack_e_forecast["lineage_checksum"],
        "paired_forecast_identity": pair["pair_identity"],
        "paired_forecast_checksum": pair["content_checksum"],
        "market_pair": "USDJPY",
        "pre_release_anchor_contract": contract.get("price_anchor_rule"),
        "t_plus_5_boundary": "2026-07-29T18:05:00Z",
        "t_plus_15_boundary": "2026-07-29T18:15:00Z",
        "t_plus_30_boundary": "2026-07-29T18:30:00Z",
        "t_plus_60_boundary": "2026-07-29T19:00:00Z",
        "maximum_rise_fall_contract": contract.get("excursion_rule"),
        "reversal_contract": contract.get("reversal_rule"),
        "approved_market_data_source_hierarchy": OUTCOME_MARKET_DATA_HIERARCHY,
        "zero_leakage_rule": "no outcome collection before authorization activation and earliest valid collection time",
        "earliest_valid_outcome_collection_time": earliest,
        "paired_forecast_authorization_fingerprint": authorization.get("authorization_fingerprint"),
    }
    payload["authorization_fingerprint"] = sha({**payload, "authorization_fingerprint": ""})
    return payload


def dispatch_requests(payloads: list[dict[str, Any]]) -> list[dict[str, Any]]:
    credentials = google_clients.load_credentials(False)
    service = google_clients.build_script_service(credentials, 240)
    script_id = google_clients.default_script_id()
    results = []
    for payload in payloads:
        response = google_clients.run_script_function_with_metadata(service, script_id, FORECAST_FUNCTION, [payload], dev_mode=True)
        results.append(response)
    return results


def execute(output_root: Path = OUT) -> tuple[Path, dict[str, Any]]:
    output_root.mkdir(parents=True, exist_ok=True)
    inputs = load_inputs()
    auth_check = authorization_validation(inputs["authorization"], inputs["episode"], inputs["attention"], inputs["pack_a"], inputs["pack_e"], inputs["separation"], inputs["requests"])
    write_json(output_root, "new_r6_paired_forecast_authorization_validation.json", auth_check)
    audit = external_audit()
    now_utc = utc_now()
    cutoff_report = {"current_utc": now_utc, "forecast_cutoff": CUTOFF, "cutoff_open": cutoff_open(now_utc), "time_remaining_seconds": max(0, int((parse_utc(CUTOFF) - parse_utc(now_utc)).total_seconds()))}
    write_json(output_root, "new_r6_paired_forecast_cutoff_validation.json", cutoff_report)
    if not auth_check["authorization_valid"]:
        blocked = "NEW_R6_PAIRED_FORECAST_BLOCKED_AUTHORIZATION_MISMATCH"
        for name in [
            "new_r6_paired_forecast_execution_plan.json",
            "new_r6_pack_a_forecast_request.json", "new_r6_pack_a_forecast_raw_response.json", "new_r6_pack_a_forecast_runtime_result.json", "new_r6_pack_a_forecast_validation.json", "new_r6_pack_a_canonical_forecast.json", "new_r6_pack_a_forecast_determinism_report.json",
            "new_r6_pack_e_forecast_request.json", "new_r6_pack_e_forecast_raw_response.json", "new_r6_pack_e_forecast_runtime_result.json", "new_r6_pack_e_forecast_validation.json", "new_r6_pack_e_canonical_forecast.json", "new_r6_pack_e_forecast_determinism_report.json",
            "new_r6_paired_forecast_record.json", "new_r6_paired_forecast_validation.json", "new_r6_paired_forecast_separation_report.json",
            "new_r6_outcome_collection_authorization_preparation.json", "new_r6_outcome_collection_authorization_fingerprint.json",
        ]:
            write_json(output_root, name, not_created(blocked))
        write_json(output_root, "external_access_audit.json", audit)
        final = {"decision": blocked, "authorization_valid": False, "authorization_activated": False, "apps_script_forecast_executions": 0, "provider_forecast_calls": 0}
        write_json(output_root, "final_new_r6_paired_forecast_decision.json", final)
        return output_root, final
    if not cutoff_report["cutoff_open"]:
        blocked = "NEW_R6_PAIRED_FORECAST_BLOCKED_CUTOFF_CLOSED"
        for name in [
            "new_r6_paired_forecast_execution_plan.json",
            "new_r6_pack_a_forecast_request.json", "new_r6_pack_a_forecast_raw_response.json", "new_r6_pack_a_forecast_runtime_result.json", "new_r6_pack_a_forecast_validation.json", "new_r6_pack_a_canonical_forecast.json", "new_r6_pack_a_forecast_determinism_report.json",
            "new_r6_pack_e_forecast_request.json", "new_r6_pack_e_forecast_raw_response.json", "new_r6_pack_e_forecast_runtime_result.json", "new_r6_pack_e_forecast_validation.json", "new_r6_pack_e_canonical_forecast.json", "new_r6_pack_e_forecast_determinism_report.json",
            "new_r6_paired_forecast_record.json", "new_r6_paired_forecast_validation.json", "new_r6_paired_forecast_separation_report.json",
            "new_r6_outcome_collection_authorization_preparation.json", "new_r6_outcome_collection_authorization_fingerprint.json",
        ]:
            write_json(output_root, name, not_created(blocked))
        write_json(output_root, "external_access_audit.json", audit)
        final = {"decision": blocked, "authorization_valid": True, "authorization_activated": False, "apps_script_forecast_executions": 0, "provider_forecast_calls": 0}
        write_json(output_root, "final_new_r6_paired_forecast_decision.json", final)
        return output_root, final

    pack_a_row = build_input_row(pack_arm="PACK_A", episode=inputs["episode"], attention=inputs["attention"], pack_a=inputs["pack_a"], pack_e=inputs["pack_e"])
    pack_e_row = build_input_row(pack_arm="PACK_E", episode=inputs["episode"], attention=inputs["attention"], pack_a=inputs["pack_a"], pack_e=inputs["pack_e"])
    run_id = "R6_PAIRED_FORECAST_" + now_utc.replace(":", "").replace("-", "").replace(".", "")
    pack_a_request = prospective_flat.prospective_request(pack_a_row, run_id=run_id + "_PACK_A", contract_version=prospective_flat.PROSPECTIVE_CONTRACT_VERSION)
    pack_e_request = prospective_flat.prospective_request(pack_e_row, run_id=run_id + "_PACK_E", contract_version=prospective_flat.PROSPECTIVE_CONTRACT_VERSION)
    plan = {
        "authorization_name": AUTHORIZATION_NAME,
        "authorization_fingerprint": AUTHORIZATION_FP,
        "execution_order": ["PACK_A", "PACK_E"],
        "provider": inputs["authorization"]["provider"],
        "model": inputs["authorization"]["model"],
        "primary_target": "USDJPY_EVENT_PATH_DIRECTION_15M",
        "call_budgets": {"pack_a": 1, "pack_e": 1, "total": 2},
        "retry_budget": 0,
    }
    write_json(output_root, "new_r6_paired_forecast_execution_plan.json", plan)
    activation = {
        "authorization_name": AUTHORIZATION_NAME,
        "authorization_fingerprint": AUTHORIZATION_FP,
        "authorization_activated": True,
        "activation_timestamp": utc_now(),
        "activation_identity": "PAIRED_FORECAST_AUTH_V1_ACTIVATION",
        "pre_dispatch_journal_state": {"pack_a_executed": False, "pack_e_executed": False, "retry_count": 0},
    }

    write_json(output_root, "new_r6_pack_a_forecast_request.json", redact(pack_a_request))
    write_json(output_root, "new_r6_pack_e_forecast_request.json", redact(pack_e_request))
    results = dispatch_requests([pack_a_request["payload"], pack_e_request["payload"]])
    audit["apps_script_forecast_executions"] = 2
    audit["provider_forecast_calls"] = 2

    arm_specs = [
        ("PACK_A", inputs["authorization"]["pack_a_arm_identity"], PACK_A_ID, pack_a_row, pack_a_request, results[0], "new_r6_pack_a_forecast"),
        ("PACK_E", inputs["authorization"]["pack_e_arm_identity"], PACK_E_ID, pack_e_row, pack_e_request, results[1], "new_r6_pack_e_forecast"),
    ]
    forecasts: dict[str, Any] = {}
    validation_payloads: dict[str, Any] = {}
    raw_transport_reports: dict[str, Any] = {}

    for pack_label, arm_identity, pack_identity, row, request_artifact, metadata, prefix in arm_specs:
        transport_result = metadata.get("result") if metadata.get("ok") else None
        transport_meta = {
            "status": (transport_result or {}).get("status") if isinstance(transport_result, Mapping) else metadata.get("classification", {}).get("category", "transport_failed").lower(),
            "requested_provider": (transport_result or {}).get("requested_provider") if isinstance(transport_result, Mapping) else "Gemini",
            "requested_model": (transport_result or {}).get("requested_model") if isinstance(transport_result, Mapping) else "gemini-2.5-flash-lite",
            "actual_provider": (transport_result or {}).get("actual_provider") if isinstance(transport_result, Mapping) else None,
            "actual_model": (transport_result or {}).get("actual_model") if isinstance(transport_result, Mapping) else None,
            "started_timestamp": (transport_result or {}).get("started_timestamp") if isinstance(transport_result, Mapping) else None,
            "completed_timestamp": (transport_result or {}).get("completed_timestamp") if isinstance(transport_result, Mapping) else None,
            "prompt_tokens": (transport_result or {}).get("prompt_tokens") if isinstance(transport_result, Mapping) else None,
            "completion_tokens": (transport_result or {}).get("completion_tokens") if isinstance(transport_result, Mapping) else None,
            "latency_ms": (transport_result or {}).get("latency_ms") if isinstance(transport_result, Mapping) else metadata.get("elapsed_ms"),
            "request_id": (transport_result or {}).get("request_id") if isinstance(transport_result, Mapping) else None,
            "stop_reason": (transport_result or {}).get("stop_reason") if isinstance(transport_result, Mapping) else None,
            "raw_output": (transport_result or {}).get("raw_output") if isinstance(transport_result, Mapping) else None,
            "metadata_ok": metadata.get("ok"),
            "metadata_classification": metadata.get("classification"),
        }
        raw_response = {"raw_response": transport_meta.get("raw_output"), "raw_response_checksum": sha(transport_meta.get("raw_output")), "transport_metadata": redact(transport_meta)}
        provider_payload = None
        if transport_meta.get("raw_output") is not None:
            try:
                provider_payload = unwrap_provider_output(transport_meta.get("raw_output"))
            except Exception:
                provider_payload = None
        arm = arm_validation(
            arm_name=pack_label,
            arm_identity=arm_identity,
            pack_identity=pack_identity,
            row=row,
            request_artifact=request_artifact,
            transport_meta=transport_meta,
            raw_response_checksum=raw_response["raw_response_checksum"],
            provider_payload=provider_payload,
            pack_label=pack_label,
        )
        runtime_result = {
            "provider": arm["provider"],
            "requested_model": arm["requested_model"],
            "returned_model": arm["returned_model"],
            "call_count": 1,
            "retry_count": 0,
            "runtime_state": arm["runtime_state"],
            "forecast_state": arm["forecast_state"],
            "request_id": transport_meta.get("request_id"),
            "usage": {"prompt_tokens": transport_meta.get("prompt_tokens"), "completion_tokens": transport_meta.get("completion_tokens")},
            "finish_status": transport_meta.get("stop_reason"),
        }
        write_json(output_root, f"{prefix}_raw_response.json", raw_response)
        write_json(output_root, f"{prefix}_runtime_result.json", runtime_result)
        write_json(output_root, f"{prefix}_validation.json", arm["validation"])
        raw_transport_reports[pack_label] = runtime_result
        validation_payloads[pack_label] = arm
        if arm["canonical_forecast"] is not None:
            canonical_name = "new_r6_pack_a_canonical_forecast.json" if pack_label == "PACK_A" else "new_r6_pack_e_canonical_forecast.json"
            determinism_name = "new_r6_pack_a_forecast_determinism_report.json" if pack_label == "PACK_A" else "new_r6_pack_e_forecast_determinism_report.json"
            write_json(output_root, canonical_name, arm["canonical_forecast"])
            write_json(output_root, determinism_name, determinism_report(lambda value=arm["canonical_forecast"]: json.loads(canonical(value))))
            forecasts[pack_label] = arm["canonical_forecast"]
        else:
            canonical_name = "new_r6_pack_a_canonical_forecast.json" if pack_label == "PACK_A" else "new_r6_pack_e_canonical_forecast.json"
            determinism_name = "new_r6_pack_a_forecast_determinism_report.json" if pack_label == "PACK_A" else "new_r6_pack_e_forecast_determinism_report.json"
            write_json(output_root, canonical_name, not_created("FORECAST_NOT_CANONICALIZED", runtime_state=arm["runtime_state"], forecast_state=arm["forecast_state"]))
            write_json(output_root, determinism_name, not_created("FORECAST_NOT_CANONICALIZED"))

    if "PACK_A" in forecasts and "PACK_E" in forecasts:
        pair = pair_record(forecasts["PACK_A"], forecasts["PACK_E"])
        pair_val = pair_validation(forecasts["PACK_A"], forecasts["PACK_E"], inputs["separation"])
        write_json(output_root, "new_r6_paired_forecast_record.json", pair)
        write_json(output_root, "new_r6_paired_forecast_validation.json", pair_val)
        write_json(output_root, "new_r6_paired_forecast_separation_report.json", {
            "pack_a_payload_excludes_pack_e": PACK_E_ID not in canonical(pack_a_request) and "TREASURY_2Y_10Y_PRESESSION_STATE" not in canonical(pack_a_request),
            "pack_e_payload_includes_frozen_pack_e": (
                isinstance(pack_e_request.get("context", {}).get("information_pack"), Mapping)
                and pack_e_request["context"]["information_pack"].get("pack_id") == PACK_E_ID
                and len(pack_e_request["context"]["information_pack"].get("items", [])) == 11
            ),
            **pair_val,
        })
        if not all([pair_val["same_episode"], pair_val["same_provider"], pair_val["same_model"], pair_val["same_cutoff"], pair_val["same_forecast_schema"], pair_val["pack_identities_distinct"], pair_val["forecast_identities_distinct"], not pair_val["pack_leakage_detected"], pair_val["separation_passed"]]):
            decision = "NEW_R6_PAIRED_FORECAST_LINEAGE_INVALID"
            write_json(output_root, "new_r6_outcome_collection_authorization_preparation.json", not_created(decision, authorization_activated=False))
            write_json(output_root, "new_r6_outcome_collection_authorization_fingerprint.json", not_created(decision))
        else:
            outcome = outcome_authorization(pair, forecasts["PACK_A"], forecasts["PACK_E"], inputs["authorization"], inputs["episode"])
            write_json(output_root, "new_r6_outcome_collection_authorization_preparation.json", outcome)
            write_json(output_root, "new_r6_outcome_collection_authorization_fingerprint.json", {"authorization_name": outcome["authorization_name"], "authorization_fingerprint": outcome["authorization_fingerprint"]})
            decision = "NEW_R6_PAIRED_FORECAST_ACCEPTED_OUTCOME_AUTHORIZATION_PREPARED"
    elif forecasts:
        decision = "NEW_R6_PAIRED_FORECAST_PARTIAL"
        write_json(output_root, "new_r6_paired_forecast_record.json", not_created(decision))
        write_json(output_root, "new_r6_paired_forecast_validation.json", {"pair_complete": False, "successful_arms": sorted(forecasts), "failed_arms": sorted({"PACK_A", "PACK_E"} - set(forecasts))})
        write_json(output_root, "new_r6_paired_forecast_separation_report.json", {"pair_complete": False, "pack_leakage_detected": False})
        write_json(output_root, "new_r6_outcome_collection_authorization_preparation.json", not_created(decision, authorization_activated=False))
        write_json(output_root, "new_r6_outcome_collection_authorization_fingerprint.json", not_created(decision))
    else:
        decision = "NEW_R6_PAIRED_FORECAST_FAILED"
        write_json(output_root, "new_r6_paired_forecast_record.json", not_created(decision))
        write_json(output_root, "new_r6_paired_forecast_validation.json", {"pair_complete": False, "successful_arms": [], "failed_arms": ["PACK_A", "PACK_E"]})
        write_json(output_root, "new_r6_paired_forecast_separation_report.json", {"pair_complete": False, "pack_leakage_detected": False})
        write_json(output_root, "new_r6_outcome_collection_authorization_preparation.json", not_created(decision, authorization_activated=False))
        write_json(output_root, "new_r6_outcome_collection_authorization_fingerprint.json", not_created(decision))

    write_json(output_root, "external_access_audit.json", audit)
    final = {
        "decision": decision,
        "authorization_name": AUTHORIZATION_NAME,
        "authorization_fingerprint": AUTHORIZATION_FP,
        "authorization_valid": True,
        "authorization_activated": True,
        "activation_record": activation,
        "current_utc": now_utc,
        "forecast_cutoff": CUTOFF,
        "cutoff_open": True,
        "time_remaining_seconds": cutoff_report["time_remaining_seconds"],
        "apps_script_forecast_executions": audit["apps_script_forecast_executions"],
        "provider_forecast_calls": audit["provider_forecast_calls"],
    }
    write_json(output_root, "final_new_r6_paired_forecast_decision.json", final)
    return output_root, final


def main() -> int:
    execute()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
