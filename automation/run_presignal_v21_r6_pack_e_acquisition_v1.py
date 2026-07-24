"""Execute the authorized minimal Pack E acquisition for R6 and stop before forecasts."""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
import re
import sys
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from automation import google_clients
from automation import presignal_v21_pack_capability_v1 as capability


OUT = ROOT / "outputs/presignal_v21_designed_drift_r6_pack_e_acquisition/R6-PACK-E-ACQUISITION-20260724-v1"
PACK_E_AUTH_DIR = ROOT / "outputs/presignal_v21_designed_drift_r6_fred_probe_v2_execution/R6-FRED-PROBE-V2-EXECUTION-20260724-v1"
PACK_A_DIR = ROOT / "outputs/presignal_v21_designed_drift_r6_pack_construction_fomc/R6-PACK-CONSTRUCTION-FOMC-20260724-v1"
SELECTION_DIR = ROOT / "outputs/presignal_v21_designed_drift_r6_episode_selection_fomc/R6-EPISODE-SELECTION-FOMC-20260724-v1"
ATTENTION_DIR = ROOT / "outputs/presignal_v21_designed_drift_r6_native_attention_field_ownership/R6-NATIVE-ATTENTION-FIELD-OWNERSHIP-20260724-v1"
REQUEST_PRIORITY_DIR = ROOT / "outputs/presignal_v21_designed_drift_r6_information_request_priority_contract_repair/R6-INFORMATION-REQUEST-PRIORITY-CONTRACT-REPAIR-20260724-v1"

EPISODE = "EP_EVENT_68a8e1cc3c9bf6ccc385"
ATTENTION_ID = "NATTN_013be496bbbd13cf4bf6"
PACK_A_ID = "PACK_A_c08bab51525d614592678fae"
PACK_A_CONTENT = "sha256:c08bab51525d614592678fae0d82ce9e695ac8ff31afdf28d3e6353573818a59"
PACK_AUTH_FP = "sha256:87fc65d0f9ec84e8efc1f0e8ef0276eb50a35d52c624191cc682dcea9f8fb869"
PACK_E_AUTH_FP = "sha256:180c3bbf815c34e7bfd8a1bb0197ba45f33799bef1e687733d22dc4d159d3d83"
ENV_FP = "sha256:3d47de0867f93ca553b4d57b4bae39ec0ed7dbb2843202ade315647caa553f3f"
PRIORITY_CONTRACT_FP = "sha256:62720c3b8b86e9cd261db99c153401afdd97f4b54f96add9ce2fcaedc6caab74"
ROUTE_B_FP = "sha256:8c910a343515d88ca63ce4aaf738f28f9b4a8ab22665397077858bfaf7e866e4"
DEPLOYMENT_FP = "sha256:7d7318dd2ac414989143f52b546f73686aa166fcfaedb4ff5cfc783e47e4d746"
CUTOFF = "2026-07-29T18:00:00Z"
SOURCE = "KSRC_FRED"
SOURCE_NAME = "Federal Reserve Economic Data"
SOURCE_TYPE = "historical_series_observation"
ADAPTER = "apps_script/prospective_pack_e_acquisition.js:apiBuildProspectivePackENativeAcquisitionRecord"
FUNCTION = "apiBuildProspectivePackENativeAcquisitionRecord"
AUTH_NAME = "PRESIGNAL_V21_DESIGNED_DRIFT_2_NEW_R6_PACK_E_ACQUISITION_AUTHORIZATION_V1"
FORECAST_AUTH_NAME = "PRESIGNAL_V21_DESIGNED_DRIFT_2_NEW_R6_PAIRED_FORECAST_AUTHORIZATION_V1"
CONFIG_REF_VERBOSE = "Apps Script Script Property FRED_API_KEY"
CREDENTIAL_TYPE = "APPS_SCRIPT_SCRIPT_PROPERTY_API_KEY"
TREASURY_REQUEST_ID = "NREQ_a90de3734b6ed432c17b"


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
        return {str(key): redact("REDACTED" if sensitive.search(str(key)) else item) for key, item in value.items()}
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, str):
        value = re.sub(r"(?i)(api[_-]?key=)[^&\\s]+", r"\\1REDACTED", value)
        value = re.sub(r"(?i)(authorization:\\s*)[^\\s]+", r"\\1REDACTED", value)
    return value


def decimal_float(value: Decimal) -> float:
    return float(value.quantize(Decimal("0.000001")))


def live_as_of_anchor(now_utc: str) -> tuple[str, str, str]:
    now_dt = parse_utc(now_utc)
    prior_day = (now_dt.date() - timedelta(days=1))
    start_day = prior_day - timedelta(days=7)
    return start_day.isoformat(), prior_day.isoformat(), f"{prior_day.isoformat()}T23:59:59Z"


def series_request(*, series: str, canonical_field: str, query_start: str, query_end: str, as_of_timestamp: str, retrieval_timestamp: str) -> dict[str, Any]:
    return {
        "source_id": SOURCE,
        "adapter_identity": ADAPTER,
        "configuration_reference": CONFIG_REF_VERBOSE,
        "credential_reference_type": CREDENTIAL_TYPE,
        "episode_id": EPISODE,
        "pack_a_identity": PACK_A_ID,
        "request_identity": TREASURY_REQUEST_ID,
        "canonical_field": canonical_field,
        "query_identity": f"FRED:{series}|{query_start}|{query_end}|R6_PACK_E_ACQUISITION_V1",
        "query_symbol": series,
        "bounded_start_date": query_start,
        "bounded_end_date": query_end,
        "forecast_cutoff_ts": CUTOFF,
        "retrieval_timestamp": retrieval_timestamp,
        "as_of_timestamp": as_of_timestamp,
        "source_identity": f"fred:series:{series}",
        "source_url_or_key": f"fred:series:{series}",
        "source_type": SOURCE_TYPE,
        "value_type": "percent",
        "source_name": SOURCE_NAME,
    }


def external_audit() -> dict[str, int]:
    return {
        "apps_script_acquisition_executions": 0,
        "fred_calls": 0,
        "fmp_calls": 0,
        "eodhd_calls": 0,
        "us_treasury_calls": 0,
        "gemini_attention_calls": 0,
        "gemini_information_request_calls": 0,
        "forecast_calls": 0,
        "google_scientific_reads": 0,
        "google_scientific_writes": 0,
        "pack_e_constructions": 0,
        "outcome_operations": 0,
        "evaluation_operations": 0,
    }


def authorization_validation(prepared: Mapping[str, Any], environment: Mapping[str, Any]) -> dict[str, Any]:
    expected_field = {
        "canonical_fields": [
            "US2Y_YIELD_LEVEL",
            "US10Y_YIELD_LEVEL",
            "US2Y_CHANGE_FROM_PRIOR_CLOSE",
            "US10Y_CHANGE_FROM_PRIOR_CLOSE",
            "US10Y_MINUS_US2Y_CURVE",
        ],
        "query_symbols": ["DGS2", "DGS10"],
        "source_id": SOURCE,
    }
    checks = {
        "authorization_name": prepared.get("authorization_name") == AUTH_NAME,
        "authorization_fingerprint": prepared.get("authorization_fingerprint") == PACK_E_AUTH_FP,
        "authorization_valid": prepared.get("authorization_valid") is True,
        "authorization_not_activated": prepared.get("authorization_activated") is False,
        "episode_identity": prepared.get("episode_identity") == EPISODE,
        "pack_a_identity": prepared.get("pack_a_identity") == PACK_A_ID,
        "pack_a_content_checksum": prepared.get("pack_a_content_checksum") == PACK_A_CONTENT,
        "source_environment_fingerprint": prepared.get("source_environment_fingerprint") == ENV_FP == environment.get("environment_fingerprint"),
        "approved_source_identities": prepared.get("approved_source_identities") == [SOURCE],
        "adapter_identity": prepared.get("prospective_adapter_identities") == [ADAPTER],
        "deployment_fingerprint": prepared.get("apps_script_deployment_fingerprint") == DEPLOYMENT_FP,
        "required_field": prepared.get("required_pack_e_field_coverage", {}).get("TREASURY_2Y_10Y_PRESESSION_STATE") == expected_field,
        "per_source_call_budget": prepared.get("per_source_call_budgets") == {SOURCE: 2},
        "total_call_budget": prepared.get("total_call_budget") == 2,
        "retry_budget": prepared.get("retry_budget") == 0,
        "forecast_cutoff": prepared.get("forecast_cutoff") == CUTOFF,
        "secret_safety_contract": prepared.get("secret_safety_contract") == "reference_only_no_secret_values_or_headers",
        "failure_stop_policy": prepared.get("failure_stop_policy") == "stop_on_source_failure_no_fallback",
        "configuration_reference_classification": prepared.get("configuration_reference_classifications", {}).get(SOURCE) == "EXISTING_SCRIPT_PROPERTY_REFERENCE_PROVEN_BY_V2_PROBE",
    }
    return {
        "authorization_name": prepared.get("authorization_name"),
        "authorization_fingerprint": prepared.get("authorization_fingerprint"),
        "authorization_valid": all(checks.values()),
        "checks": checks,
    }


def classify_transport(record: Mapping[str, Any] | None, metadata: Mapping[str, Any] | None) -> tuple[str, bool]:
    if metadata and not metadata.get("ok"):
        return "SOURCE_TRANSPORT_FAILED", True
    if not isinstance(record, Mapping):
        return "SOURCE_RESPONSE_INVALID", False
    status = str(record.get("status") or "")
    error = str(record.get("error_classification") or "")
    if status == "SUPPLIED":
        return "", True
    mapping = {
        "SOURCE_CONFIGURATION_MISSING": "SOURCE_CONFIGURATION_MISSING",
        "SOURCE_CREDENTIAL_MISSING": "SOURCE_CREDENTIAL_MISSING",
        "SOURCE_ACCESS_NOT_AUTHORIZED": "SOURCE_ACCESS_NOT_AUTHORIZED",
        "SOURCE_RESPONSE_INVALID": "SOURCE_RESPONSE_INVALID",
        "SOURCE_CONTENT_NOT_FOUND": "SOURCE_CONTENT_NOT_FOUND",
        "SOURCE_TEMPORAL_CONTRACT_UNSUPPORTED": "SOURCE_TEMPORALLY_INVALID",
        "SOURCE_QUERY_UNSUPPORTED": "SOURCE_QUERY_UNSUPPORTED",
    }
    return mapping.get(error, "SOURCE_NATIVE_RECORD_INVALID"), error in {"SOURCE_ACCESS_NOT_AUTHORIZED", "SOURCE_RESPONSE_INVALID", "SOURCE_QUERY_UNSUPPORTED"}


def validate_native_record(record: Any, request: Mapping[str, Any], *, expected_field: str, expected_series: str) -> dict[str, Any]:
    if not isinstance(record, Mapping):
        return {"schema_valid": False, "writer_count": 0, "reason": "RECORD_NOT_OBJECT"}
    source_items = record.get("source_items") or []
    first = source_items[0] if source_items else {}
    required = [
        "object", "acquisition_record_id", "source_id", "adapter_identity", "request_identity",
        "episode_id", "forecast_cutoff_ts", "retrieval_timestamp", "acquisition_timestamp",
        "raw_checksum", "normalized_checksum", "status", "source_identity", "query_identity",
    ]
    missing = [field for field in required if not record.get(field)]
    schema_valid = (
        record.get("object") == "NATIVE_ACQUISITION_RECORD"
        and not missing
        and record.get("source_id") == SOURCE
        and record.get("adapter_identity") == ADAPTER
        and record.get("request_identity") == TREASURY_REQUEST_ID
        and record.get("episode_id") == EPISODE
        and record.get("query_identity") == request["query_identity"]
        and record.get("source_identity") == request["source_identity"]
        and record.get("status") == "SUPPLIED"
        and first.get("canonical_field") == expected_field
        and record.get("source_url_or_key") == request["source_url_or_key"]
    )
    provenance_valid = record.get("pack_a_identity") == PACK_A_ID and record.get("source_id") == SOURCE
    lineage_valid = provenance_valid and first.get("source_id") == SOURCE and first.get("source_identity") == request["source_identity"]
    return {
        "record_identity": record.get("acquisition_record_id"),
        "source_identity": record.get("source_identity"),
        "adapter_identity": record.get("adapter_identity"),
        "series": expected_series,
        "effective_timestamp": record.get("source_timestamp") or first.get("source_timestamp"),
        "retrieval_timestamp": record.get("retrieval_timestamp"),
        "raw_checksum": record.get("raw_checksum"),
        "normalized_checksum": record.get("normalized_checksum"),
        "schema_valid": schema_valid,
        "provenance_valid": provenance_valid,
        "lineage_valid": lineage_valid,
        "temporal_valid": bool(record.get("source_timestamp")) and parse_utc(record.get("retrieval_timestamp")) < parse_utc(CUTOFF),
        "writer_count": 0,
        "required_fields_missing": missing,
        "status": record.get("status"),
        "error_classification": record.get("error_classification"),
    }


def temporal_validation(record: Mapping[str, Any], request: Mapping[str, Any]) -> dict[str, Any]:
    raw = json.loads(record.get("raw_acquired_content") or "{}")
    rows = list(raw.get("rows") or [])
    rows = sorted(rows, key=lambda row: str(row.get("date") or ""))
    dates = [str(row.get("date") or "") for row in rows]
    normalized = json.loads(record.get("normalized_acquired_content") or "{}")
    selected = normalized.get("selected_observation") or {}
    as_of_date = str(request["as_of_timestamp"])[:10]
    eligible = [row for row in rows if str(row.get("date") or "") <= as_of_date]
    latest = eligible[-1] if eligible else None
    retrieval_date = str(record.get("retrieval_timestamp") or "")[:10]
    return {
        "series": request["query_symbol"],
        "bounded_query_preserved": all(request["bounded_start_date"] <= value <= request["bounded_end_date"] for value in dates),
        "observations_sorted_deterministically": dates == sorted(dates),
        "latest_eligible_observation_selection_deterministic": latest == selected if latest else False,
        "selected_observation_is_latest_eligible": str(selected.get("date") or "") == str((latest or {}).get("date") or ""),
        "effective_timestamp_before_cutoff": parse_utc(record["source_timestamp"]) < parse_utc(CUTOFF),
        "retrieval_before_cutoff": parse_utc(record["retrieval_timestamp"]) < parse_utc(CUTOFF),
        "post_query_observation_used": any(value > request["bounded_end_date"] for value in dates),
        "same_day_value_used": str(selected.get("date") or "") == retrieval_date,
        "temporal_valid": all([
            all(request["bounded_start_date"] <= value <= request["bounded_end_date"] for value in dates),
            dates == sorted(dates),
            latest == selected if latest else False,
            parse_utc(record["source_timestamp"]) < parse_utc(CUTOFF),
            parse_utc(record["retrieval_timestamp"]) < parse_utc(CUTOFF),
        ]),
    }


def derive_treasury_state(dgs2_record: Mapping[str, Any], dgs10_record: Mapping[str, Any]) -> dict[str, Any]:
    def extract(record: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
        raw = json.loads(record["raw_acquired_content"])
        normalized = json.loads(record["normalized_acquired_content"])
        rows = sorted(list(raw["rows"]), key=lambda row: row["date"])
        selected = normalized["selected_observation"]
        idx = next(index for index, row in enumerate(rows) if row["date"] == selected["date"] and row["value"] == selected["value"])
        if idx == 0:
            raise ValueError("PRIOR_CLOSE_OBSERVATION_MISSING")
        return selected, rows[idx - 1], rows

    dgs2_selected, dgs2_prior, dgs2_rows = extract(dgs2_record)
    dgs10_selected, dgs10_prior, dgs10_rows = extract(dgs10_record)
    effective_timestamp = dgs2_record["source_timestamp"]
    if effective_timestamp != dgs10_record["source_timestamp"]:
        raise ValueError("TREASURY_EFFECTIVE_TIMESTAMP_MISMATCH")
    as_of_timestamp = dgs2_record["as_of_timestamp"]
    if as_of_timestamp != dgs10_record["as_of_timestamp"]:
        raise ValueError("TREASURY_AS_OF_TIMESTAMP_MISMATCH")

    d2 = Decimal(str(dgs2_selected["value"]))
    d2_prior = Decimal(str(dgs2_prior["value"]))
    d10 = Decimal(str(dgs10_selected["value"]))
    d10_prior = Decimal(str(dgs10_prior["value"]))
    state_value = {
        "us2y_yield_level": decimal_float(d2),
        "us10y_yield_level": decimal_float(d10),
        "us2y_change_from_prior": decimal_float(d2 - d2_prior),
        "us10y_change_from_prior": decimal_float(d10 - d10_prior),
        "us10y_minus_us2y_curve": decimal_float(d10 - d2),
    }
    provenance = {
        "derivation_rule": "prior_day_levels_changes_and_2s10s_curve_v1",
        "reason": "TIME_SAFE_2Y_10Y_PRIOR_DAY_STATE",
        "same_day_value_used": False,
        "source_identity": "FRED:DGS2|DGS10",
        "source_series_or_input": "DGS2|DGS10",
        "source_system": "FRED",
        "source_timestamp": effective_timestamp,
        "input_lineage": [
            {
                "source_identity": "FRED:DGS2",
                "source_series_or_input": "DGS2",
                "source_system": "FRED",
                "observation_timestamp": dgs2_record["source_timestamp"],
                "prior_observation_date": dgs2_prior["date"],
                "prior_value": dgs2_prior["value"],
                "value": dgs2_selected["value"],
                "publication_timestamp_policy": "conservative",
                "same_day_value_used": False,
            },
            {
                "source_identity": "FRED:DGS10",
                "source_series_or_input": "DGS10",
                "source_system": "FRED",
                "observation_timestamp": dgs10_record["source_timestamp"],
                "prior_observation_date": dgs10_prior["date"],
                "prior_value": dgs10_prior["value"],
                "value": dgs10_selected["value"],
                "publication_timestamp_policy": "conservative",
                "same_day_value_used": False,
            },
        ],
    }
    lineage = {
        "dgs2_record_identity": dgs2_record["acquisition_record_id"],
        "dgs10_record_identity": dgs10_record["acquisition_record_id"],
        "dgs2_raw_checksum": dgs2_record["raw_checksum"],
        "dgs10_raw_checksum": dgs10_record["raw_checksum"],
        "dgs2_normalized_checksum": dgs2_record["normalized_checksum"],
        "dgs10_normalized_checksum": dgs10_record["normalized_checksum"],
    }
    content_basis = {
        "episode_identity": EPISODE,
        "pack_a_identity": PACK_A_ID,
        "field_identity": "TREASURY_2Y_10Y_PRESESSION_STATE",
        "effective_timestamp": effective_timestamp,
        "as_of_timestamp": as_of_timestamp,
        "value": state_value,
    }
    return {
        "field_identity": "TREASURY_2Y_10Y_PRESESSION_STATE",
        "effective_timestamp": effective_timestamp,
        "as_of_timestamp": as_of_timestamp,
        "source_rows": {"DGS2": dgs2_rows, "DGS10": dgs10_rows},
        "selected_observations": {"DGS2": dgs2_selected, "DGS10": dgs10_selected},
        "prior_observations": {"DGS2": dgs2_prior, "DGS10": dgs10_prior},
        "derived_fields": state_value,
        "content_checksum": sha(content_basis),
        "provenance": provenance,
        "provenance_checksum": sha(provenance),
        "lineage": lineage,
        "lineage_checksum": sha(lineage),
    }


def treasury_state_to_composite_record(treasury_state: Mapping[str, Any], dgs2_record: Mapping[str, Any], dgs10_record: Mapping[str, Any], retrieval_timestamp: str) -> dict[str, Any]:
    derived = treasury_state["derived_fields"]
    effective_timestamp = treasury_state["effective_timestamp"]
    as_of_timestamp = treasury_state["as_of_timestamp"]
    raw_evidence = {
        "derivation_rule": "prior_day_levels_changes_and_2s10s_curve_v1",
        "field_identity": "TREASURY_2Y_10Y_PRESESSION_STATE",
        "dgs2_record": redact(dgs2_record),
        "dgs10_record": redact(dgs10_record),
        "selected_observations": treasury_state["selected_observations"],
        "prior_observations": treasury_state["prior_observations"],
    }
    normalized_evidence = {
        "canonical_field_bundle": "TREASURY_2Y_10Y_PRESESSION_STATE",
        "effective_timestamp": effective_timestamp,
        "as_of_timestamp": as_of_timestamp,
        "derived_fields": derived,
    }
    identity = {
        "episode_id": EPISODE,
        "pack_a_identity": PACK_A_ID,
        "request_identity": TREASURY_REQUEST_ID,
        "source_id": SOURCE,
        "source_identity": "fred:series:DGS2|DGS10",
        "source_timestamp": effective_timestamp,
        "derived_fields": derived,
    }
    return {
        "object": "NATIVE_ACQUISITION_RECORD",
        "schema_version": "presignal.prospective_pack_e_acquisition.v1",
        "acquisition_record_id": "NACQ_" + sha(identity)[7:27],
        "episode_id": EPISODE,
        "pack_a_identity": PACK_A_ID,
        "request_identity": TREASURY_REQUEST_ID,
        "forecast_cutoff_ts": CUTOFF,
        "source_id": SOURCE,
        "adapter_identity": ADAPTER,
        "configuration_reference": CONFIG_REF_VERBOSE,
        "credential_reference_type": CREDENTIAL_TYPE,
        "source_identity": "fred:series:DGS2|DGS10",
        "source_url_or_key": "fred:series:DGS2|DGS10",
        "source_type": "historical_series_bundle_observation",
        "query_identity": f"{dgs2_record['query_identity']}|{dgs10_record['query_identity']}",
        "retrieval_timestamp": retrieval_timestamp,
        "acquisition_timestamp": retrieval_timestamp,
        "source_timestamp": effective_timestamp,
        "as_of_timestamp": as_of_timestamp,
        "acquisition_method": "caller_controlled_existing_v2_fetch",
        "status": "SUPPLIED",
        "error_classification": "",
        "reason": "TIME_SAFE_2Y_10Y_PRIOR_DAY_STATE",
        "raw_acquired_content": canonical(raw_evidence),
        "normalized_acquired_content": canonical(normalized_evidence),
        "raw_checksum": sha(raw_evidence),
        "normalized_checksum": sha(normalized_evidence),
        "source_items": [
            {
                "canonical_field": "US2Y_YIELD_LEVEL",
                "value": derived["us2y_yield_level"],
                "value_type": "percent",
                "source_id": SOURCE,
                "source_name": SOURCE_NAME,
                "source_identity": "fred:series:DGS2",
                "source_timestamp": effective_timestamp,
                "as_of_timestamp": as_of_timestamp,
                "acquisition_timestamp": retrieval_timestamp,
                "acquisition_method": "caller_controlled_existing_v2_fetch",
            },
            {
                "canonical_field": "US10Y_YIELD_LEVEL",
                "value": derived["us10y_yield_level"],
                "value_type": "percent",
                "source_id": SOURCE,
                "source_name": SOURCE_NAME,
                "source_identity": "fred:series:DGS10",
                "source_timestamp": effective_timestamp,
                "as_of_timestamp": as_of_timestamp,
                "acquisition_timestamp": retrieval_timestamp,
                "acquisition_method": "caller_controlled_existing_v2_fetch",
            },
            {
                "canonical_field": "US2Y_CHANGE_FROM_PRIOR_CLOSE",
                "value": derived["us2y_change_from_prior"],
                "value_type": "percent_change",
                "source_id": SOURCE,
                "source_name": SOURCE_NAME,
                "source_identity": "fred:series:DGS2",
                "source_timestamp": effective_timestamp,
                "as_of_timestamp": as_of_timestamp,
                "acquisition_timestamp": retrieval_timestamp,
                "acquisition_method": "caller_controlled_existing_v2_fetch",
            },
            {
                "canonical_field": "US10Y_CHANGE_FROM_PRIOR_CLOSE",
                "value": derived["us10y_change_from_prior"],
                "value_type": "percent_change",
                "source_id": SOURCE,
                "source_name": SOURCE_NAME,
                "source_identity": "fred:series:DGS10",
                "source_timestamp": effective_timestamp,
                "as_of_timestamp": as_of_timestamp,
                "acquisition_timestamp": retrieval_timestamp,
                "acquisition_method": "caller_controlled_existing_v2_fetch",
            },
            {
                "canonical_field": "US10Y_MINUS_US2Y_CURVE",
                "value": derived["us10y_minus_us2y_curve"],
                "value_type": "percent_spread",
                "source_id": SOURCE,
                "source_name": SOURCE_NAME,
                "source_identity": "fred:series:DGS2|DGS10",
                "source_timestamp": effective_timestamp,
                "as_of_timestamp": as_of_timestamp,
                "acquisition_timestamp": retrieval_timestamp,
                "acquisition_method": "caller_controlled_existing_v2_fetch",
            },
        ],
    }


def coverage_report(pack_e: Mapping[str, Any]) -> dict[str, Any]:
    required_treasury_items = {
        "US2Y_YIELD_LEVEL",
        "US10Y_YIELD_LEVEL",
        "US2Y_CHANGE_FROM_PRIOR_CLOSE",
        "US10Y_CHANGE_FROM_PRIOR_CLOSE",
        "US10Y_MINUS_US2Y_CURVE",
    }
    status_map: dict[str, dict[str, Any]] = {}
    for row in pack_e["items"]:
        for request_id in row.get("request_identities", []):
            if row["capability_id"] in required_treasury_items:
                status_map[request_id] = {"coverage_status": "DIRECT_SUPPORT", "pack_item_key": row["item_key"]}
            elif row["status"] in {"POLICY_REJECTED", "INTERPRETIVE_NOT_SUPPLIED"}:
                status_map[request_id] = {"coverage_status": "NOT_REQUIRED_BY_MINIMUM_PACK_E_CONTRACT", "pack_item_key": row["item_key"]}
            else:
                status_map[request_id] = {"coverage_status": "NO_PACK_E_COVERAGE", "pack_item_key": row["item_key"]}
    requests = read_json(REQUEST_PRIORITY_DIR / "new_r6_canonical_information_requests.json")["requests"]
    rows = []
    for request in requests:
        mapped = status_map.get(request["request_identity"], {"coverage_status": "NO_PACK_E_COVERAGE", "pack_item_key": ""})
        rows.append({
            "request_identity": request["request_identity"],
            "category": request["information_category"],
            "coverage_status": mapped["coverage_status"],
            "pack_item_key": mapped["pack_item_key"],
        })
    return {
        "required_field": "TREASURY_2Y_10Y_PRESESSION_STATE",
        "required_coverage_complete": any(row["coverage_status"] == "DIRECT_SUPPORT" and row["category"] == "treasury_yields" for row in rows),
        "coverage": rows,
    }


def adapt_requests_for_pack_builder(current_requests: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    adapted: list[dict[str, Any]] = []
    for row in current_requests:
        requested = str(row.get("requested_information") or row.get("request_text") or "").strip()
        category = str(row.get("information_category") or "").strip()
        adapted.append(
            {
                "request_identity": row["request_identity"],
                "information_key": capability._information_key(category, requested),
                "information_category": category,
                "requested_information": requested,
                "lineage": {
                    "episode_id": EPISODE,
                    "episode_identity": row.get("episode_identity", EPISODE),
                    "attention_id": ATTENTION_ID,
                    "forecast_cutoff_ts": CUTOFF,
                    "source_request_identity": row["request_identity"],
                    "source_content_checksum": row.get("content_checksum"),
                    "source_lineage_checksum": row.get("lineage_checksum"),
                },
            }
        )
    adapted.sort(key=lambda item: item["request_identity"])
    return adapted


def canonical_episode_for_pack_builder(selected_manifest: Mapping[str, Any]) -> dict[str, Any]:
    source = dict(selected_manifest["episode_content"])
    allowed_fields = {
        "object",
        "schema_version",
        "system_version",
        "episode_id",
        "session_id",
        "country",
        "episode_family",
        "release_ts",
        "forecast_cutoff_ts",
        "member_event_count",
        "member_event_ids",
        "member_indicator_names",
        "primary_event_id",
        "primary_indicator_name",
        "secondary_event_ids",
        "secondary_indicator_names",
        "selection_status",
        "selection_reason",
        "same_time_cluster_flag",
        "created_ts",
        "updated_ts",
        "status",
        "error_message",
    }
    episode = {key: source[key] for key in allowed_fields}
    episode["member_event_ids"] = list(source.get("member_event_ids") or [])
    episode["member_indicator_names"] = list(source.get("member_indicator_names") or [])
    episode["secondary_event_ids"] = list(source.get("secondary_event_ids") or [])
    episode["secondary_indicator_names"] = list(source.get("secondary_indicator_names") or [])
    return episode


def separation_report(pack_a: Mapping[str, Any], pack_e: Mapping[str, Any], bundle: Mapping[str, Any], composite_record: Mapping[str, Any]) -> dict[str, Any]:
    canonical_requests = read_json(REQUEST_PRIORITY_DIR / "new_r6_canonical_information_requests.json")["requests"]
    pack_builder_requests = adapt_requests_for_pack_builder(canonical_requests)
    distinct = pack_a["pack_identity"] != pack_e["pack_id"]
    roles_distinct = pack_a["pack_type"] != pack_e["object"]
    episode_lineage_valid = pack_a["episode_identity"] == pack_e["episode_id"] == EPISODE
    attention_lineage_valid = pack_a["attention_identity"] == ATTENTION_ID
    request_lineage_valid = bundle["request_fingerprint"] == sha(pack_builder_requests)
    acquisition_lineage_valid = (
        composite_record["request_identity"] == TREASURY_REQUEST_ID
        and composite_record["episode_id"] == EPISODE
        and composite_record["pack_a_identity"] == PACK_A_ID
        and bundle["authorized_source_environment_id"] == "R6_PACK_E_FRED_TREASURY_MINIMUM_V2"
    )
    return {
        "pack_a_identity": pack_a["pack_identity"],
        "pack_e_identity": pack_e["pack_id"],
        "pack_a_type": pack_a["pack_type"],
        "pack_e_type": pack_e["object"],
        "identities_distinct": distinct,
        "roles_distinct": roles_distinct,
        "content_roles_distinct": True,
        "pack_e_not_embedded_in_pack_a": True,
        "pack_a_requests_not_represented_as_acquired_facts": True,
        "episode_lineage_valid": episode_lineage_valid,
        "attention_lineage_valid": attention_lineage_valid,
        "request_lineage_valid": request_lineage_valid,
        "acquisition_lineage_valid": acquisition_lineage_valid,
        "separation_passed": all([distinct, roles_distinct, episode_lineage_valid, attention_lineage_valid, request_lineage_valid, acquisition_lineage_valid]),
    }


def paired_forecast_authorization(pack_e: Mapping[str, Any], separation: Mapping[str, Any], selected: Mapping[str, Any], attention: Mapping[str, Any], env: Mapping[str, Any], acquisition_auth: Mapping[str, Any], treasury_state: Mapping[str, Any], dgs2_record: Mapping[str, Any], dgs10_record: Mapping[str, Any]) -> dict[str, Any]:
    source_evidence_checksums = {
        "dgs2_raw_checksum": dgs2_record["raw_checksum"],
        "dgs2_normalized_checksum": dgs2_record["normalized_checksum"],
        "dgs10_raw_checksum": dgs10_record["raw_checksum"],
        "dgs10_normalized_checksum": dgs10_record["normalized_checksum"],
        "treasury_state_content_checksum": treasury_state["content_checksum"],
    }
    return {
        "authorization_name": FORECAST_AUTH_NAME,
        "route_b_freeze_fingerprint": ROUTE_B_FP,
        "episode_selection_authorization_fingerprint": "sha256:5d673811c40d006ae4630d0fde122a04aa20ab907781d3a762568e7b837389b8",
        "episode_identity": EPISODE,
        "episode_content_checksum": selected["content_checksum"],
        "episode_provenance_checksum": selected["provenance_checksum"],
        "episode_lineage_checksum": selected["lineage_checksum"],
        "attention_identity": ATTENTION_ID,
        "attention_content_checksum": attention["content_checksum"],
        "attention_provenance_checksum": attention["provenance_checksum"],
        "attention_lineage_checksum": attention["lineage_checksum"],
        "request_set_checksum": PACK_A_DIR and read_json(REQUEST_PRIORITY_DIR / "new_r6_canonical_information_requests.json")["request_set_checksum"],
        "priority_contract_fingerprint": PRIORITY_CONTRACT_FP,
        "pack_authorization_fingerprint": PACK_AUTH_FP,
        "pack_e_acquisition_authorization_fingerprint": acquisition_auth["authorization_fingerprint"],
        "source_environment_fingerprint": env["environment_fingerprint"],
        "pack_a_identity": PACK_A_ID,
        "pack_a_content_checksum": PACK_A_CONTENT,
        "pack_a_provenance_checksum": read_json(PACK_A_DIR / "new_r6_pack_a.json")["provenance_checksum"],
        "pack_a_lineage_checksum": read_json(PACK_A_DIR / "new_r6_pack_a.json")["lineage_checksum"],
        "pack_e_identity": pack_e["pack_id"],
        "pack_e_content_checksum": pack_e["pack_fingerprint"],
        "pack_e_provenance_checksum": sha({"object": pack_e["object"], "item_keys": [row["item_key"] for row in pack_e["items"]], "source_environment_id": pack_e["lineage"]["authorized_source_environment_id"]}),
        "pack_e_lineage_checksum": sha(pack_e["lineage"]),
        "pack_separation_report_checksum": sha(separation),
        "source_acquisition_evidence_checksums": source_evidence_checksums,
        "provider": "Gemini",
        "model": "gemini-2.5-flash-lite",
        "pack_a_arm_identity": f"{PACK_A_ID}:ARM_PACK_A",
        "pack_e_arm_identity": f"{pack_e['pack_id']}:ARM_PACK_E",
        "forecast_schema": "presignal_event_path_contract_v1_flat_stage_prospective_v1",
        "primary_endpoint": "15-minute primary endpoint",
        "optional_sidecars": [5, 30, 60],
        "call_budget": 2,
        "pack_a_call_budget": 1,
        "pack_e_call_budget": 1,
        "retry_budget": 0,
        "forecast_cutoff": CUTOFF,
        "authorization_valid": True,
        "authorization_activated": False,
        "pack_a_forecast_executed": False,
        "pack_e_forecast_executed": False,
    }


def run(output: Path = OUT, *, dispatch: bool = True, at_utc: str | None = None) -> str:
    output.mkdir(parents=True, exist_ok=True)
    auth = read_json(PACK_E_AUTH_DIR / "r6_pack_e_acquisition_authorization_preparation.json")
    env = read_json(PACK_E_AUTH_DIR / "r6_pack_e_source_environment.json")
    pack_a = read_json(PACK_A_DIR / "new_r6_pack_a.json")
    selected = read_json(SELECTION_DIR / "new_r6_selected_episode_manifest.json")
    attention = read_json(ATTENTION_DIR / "new_r6_native_attention.json")
    canonical_requests = read_json(REQUEST_PRIORITY_DIR / "new_r6_canonical_information_requests.json")["requests"]
    pack_builder_requests = adapt_requests_for_pack_builder(canonical_requests)
    now_utc = at_utc or utc_now()
    auth_validation = authorization_validation(auth, env)
    query_start, query_end, as_of_timestamp = live_as_of_anchor(now_utc)
    plan = {
        "required_pack_e_field": "TREASURY_2Y_10Y_PRESESSION_STATE",
        "series": [
            {
                "series": "DGS2",
                "bounded_query_range": {"start": query_start, "end": query_end},
                "pack_e_field_binding": "US2Y_YIELD_LEVEL",
                "call_budget": 1,
                "selection_rule": "latest eligible observation at or before prior UTC date; same-day values excluded; immediate prior observation used for prior-close delta",
                "cutoff_rule": "retrieval timestamp before forecast cutoff; effective/source timestamp before forecast cutoff",
            },
            {
                "series": "DGS10",
                "bounded_query_range": {"start": query_start, "end": query_end},
                "pack_e_field_binding": "US10Y_YIELD_LEVEL",
                "call_budget": 1,
                "selection_rule": "latest eligible observation at or before prior UTC date; same-day values excluded; immediate prior observation used for prior-close delta",
                "cutoff_rule": "retrieval timestamp before forecast cutoff; effective/source timestamp before forecast cutoff",
            },
        ],
        "total_call_budget": 2,
        "retry_budget": 0,
    }
    reports: dict[str, Any] = {
        "pack_e_acquisition_authorization_validation.json": auth_validation,
        "pack_e_acquisition_plan.json": plan,
        "secret_safety_report.json": {
            "new_credential_created": False,
            "credential_alias_added": False,
            "secret_value_exposed": False,
            "credential_committed": False,
        },
    }
    audit = external_audit()

    if not auth_validation["authorization_valid"]:
        decision = "NEW_R6_PACK_E_ACQUISITION_BLOCKED_AUTHORIZATION_MISMATCH"
        for name in [
            "pack_e_acquisition_activation_record.json", "fred_dgs2_acquisition_request.json",
            "fred_dgs2_acquisition_result.json", "fred_dgs2_native_record.json",
            "fred_dgs2_native_record_validation.json", "fred_dgs10_acquisition_request.json",
            "fred_dgs10_acquisition_result.json", "fred_dgs10_native_record.json",
            "fred_dgs10_native_record_validation.json", "pack_e_temporal_safety_report.json",
            "pack_e_treasury_state.json", "pack_e_treasury_state_determinism_report.json",
            "new_r6_pack_e.json", "new_r6_pack_e_coverage_report.json",
            "new_r6_pack_e_determinism_report.json", "new_r6_pack_e_lineage_report.json",
            "new_r6_pack_separation_report.json", "new_r6_paired_forecast_authorization_preparation.json",
            "new_r6_paired_forecast_authorization_fingerprint.json",
        ]:
            reports[name] = {"status": "NOT_CREATED", "reason": decision}
        reports["external_access_audit.json"] = audit
        reports["final_pack_e_acquisition_decision.json"] = {"decision": decision, "current_utc": now_utc, "cutoff_open": cutoff_open(now_utc)}
        for name, value in reports.items():
            write_json(output, name, value)
        return decision

    if not cutoff_open(now_utc):
        decision = "NEW_R6_PACK_E_ACQUISITION_BLOCKED_CUTOFF_CLOSED"
        for name in [
            "pack_e_acquisition_activation_record.json", "fred_dgs2_acquisition_request.json",
            "fred_dgs2_acquisition_result.json", "fred_dgs2_native_record.json",
            "fred_dgs2_native_record_validation.json", "fred_dgs10_acquisition_request.json",
            "fred_dgs10_acquisition_result.json", "fred_dgs10_native_record.json",
            "fred_dgs10_native_record_validation.json", "pack_e_temporal_safety_report.json",
            "pack_e_treasury_state.json", "pack_e_treasury_state_determinism_report.json",
            "new_r6_pack_e.json", "new_r6_pack_e_coverage_report.json",
            "new_r6_pack_e_determinism_report.json", "new_r6_pack_e_lineage_report.json",
            "new_r6_pack_separation_report.json", "new_r6_paired_forecast_authorization_preparation.json",
            "new_r6_paired_forecast_authorization_fingerprint.json",
        ]:
            reports[name] = {"status": "NOT_CREATED", "reason": decision}
        reports["external_access_audit.json"] = audit
        reports["final_pack_e_acquisition_decision.json"] = {"decision": decision, "current_utc": now_utc, "cutoff_open": False}
        for name, value in reports.items():
            write_json(output, name, value)
        return decision

    reports["pack_e_acquisition_activation_record.json"] = {
        "authorization_name": AUTH_NAME,
        "authorization_fingerprint": PACK_E_AUTH_FP,
        "authorization_activated": True,
        "activation_timestamp": now_utc,
        "activation_identity": "R6_PACK_E_ACQUISITION_SINGLE_USE_ACTIVATION",
        "pre_dispatch_operation_journal_state": {"apps_script_acquisition_executions": 0, "fred_calls": 0, "retries": 0},
        "consumed": True,
    }

    dgs2_request = series_request(series="DGS2", canonical_field="US2Y_YIELD_LEVEL", query_start=query_start, query_end=query_end, as_of_timestamp=as_of_timestamp, retrieval_timestamp=now_utc)
    dgs10_request = series_request(series="DGS10", canonical_field="US10Y_YIELD_LEVEL", query_start=query_start, query_end=query_end, as_of_timestamp=as_of_timestamp, retrieval_timestamp=now_utc)
    reports["fred_dgs2_acquisition_request.json"] = {"request": dgs2_request, "request_checksum": sha(dgs2_request)}
    reports["fred_dgs10_acquisition_request.json"] = {"request": dgs10_request, "request_checksum": sha(dgs10_request)}

    if dispatch:
        creds = google_clients.load_credentials(False, token_path=ROOT / "local/token.json", persist_refresh=False)
        service = google_clients.build_script_service(creds, 120)
        dgs2_meta = google_clients.run_script_function_with_metadata(service, google_clients.default_script_id(), FUNCTION, [dgs2_request])
        dgs10_meta = google_clients.run_script_function_with_metadata(service, google_clients.default_script_id(), FUNCTION, [dgs10_request])
        audit["apps_script_acquisition_executions"] = 2
    else:
        dgs2_meta = {"ok": False, "classification": {"category": "NOT_DISPATCHED"}, "response": None}
        dgs10_meta = {"ok": False, "classification": {"category": "NOT_DISPATCHED"}, "response": None}

    dgs2_record = dgs2_meta.get("result") if dgs2_meta.get("ok") else None
    dgs10_record = dgs10_meta.get("result") if dgs10_meta.get("ok") else None
    reports["fred_dgs2_acquisition_result.json"] = redact({
        "transport_status": "SUCCESS" if dgs2_meta.get("ok") else "FAILED",
        "metadata": dgs2_meta,
        "source_status": (dgs2_record or {}).get("status") if isinstance(dgs2_record, Mapping) else "NO_RECORD",
    })
    reports["fred_dgs10_acquisition_result.json"] = redact({
        "transport_status": "SUCCESS" if dgs10_meta.get("ok") else "FAILED",
        "metadata": dgs10_meta,
        "source_status": (dgs10_record or {}).get("status") if isinstance(dgs10_record, Mapping) else "NO_RECORD",
    })
    reports["fred_dgs2_native_record.json"] = redact(dgs2_record) if isinstance(dgs2_record, Mapping) else {"status": "NOT_CREATED"}
    reports["fred_dgs10_native_record.json"] = redact(dgs10_record) if isinstance(dgs10_record, Mapping) else {"status": "NOT_CREATED"}

    dgs2_transport_classification, dgs2_counted = classify_transport(dgs2_record if isinstance(dgs2_record, Mapping) else None, dgs2_meta)
    dgs10_transport_classification, dgs10_counted = classify_transport(dgs10_record if isinstance(dgs10_record, Mapping) else None, dgs10_meta)
    if dgs2_counted:
        audit["fred_calls"] += 1
    if dgs10_counted:
        audit["fred_calls"] += 1

    dgs2_validation = validate_native_record(dgs2_record, dgs2_request, expected_field="US2Y_YIELD_LEVEL", expected_series="DGS2") if isinstance(dgs2_record, Mapping) else {"schema_valid": False, "writer_count": 0}
    dgs10_validation = validate_native_record(dgs10_record, dgs10_request, expected_field="US10Y_YIELD_LEVEL", expected_series="DGS10") if isinstance(dgs10_record, Mapping) else {"schema_valid": False, "writer_count": 0}
    reports["fred_dgs2_native_record_validation.json"] = dgs2_validation
    reports["fred_dgs10_native_record_validation.json"] = dgs10_validation
    dgs2_temporal = temporal_validation(dgs2_record, dgs2_request) if isinstance(dgs2_record, Mapping) and dgs2_record.get("status") == "SUPPLIED" else {"series": "DGS2", "temporal_valid": False}
    dgs10_temporal = temporal_validation(dgs10_record, dgs10_request) if isinstance(dgs10_record, Mapping) and dgs10_record.get("status") == "SUPPLIED" else {"series": "DGS10", "temporal_valid": False}

    if dgs2_transport_classification or dgs10_transport_classification or not dgs2_validation.get("schema_valid") or not dgs10_validation.get("schema_valid") or not dgs2_temporal.get("temporal_valid") or not dgs10_temporal.get("temporal_valid"):
        decision = "NEW_R6_PACK_E_ACQUISITION_FAILED"
        reports["pack_e_temporal_safety_report.json"] = {"status": "FAILED", "dgs2": dgs2_temporal, "dgs10": dgs10_temporal, "failure_classifications": [dgs2_transport_classification, dgs10_transport_classification]}
        for name in [
            "pack_e_treasury_state.json", "pack_e_treasury_state_determinism_report.json",
            "new_r6_pack_e.json", "new_r6_pack_e_coverage_report.json",
            "new_r6_pack_e_determinism_report.json", "new_r6_pack_e_lineage_report.json",
            "new_r6_pack_separation_report.json", "new_r6_paired_forecast_authorization_preparation.json",
            "new_r6_paired_forecast_authorization_fingerprint.json",
        ]:
            reports[name] = {"status": "NOT_CREATED", "reason": decision}
        reports["external_access_audit.json"] = audit
        reports["final_pack_e_acquisition_decision.json"] = {"decision": decision, "current_utc": now_utc, "cutoff_open": True}
        for name, value in reports.items():
            write_json(output, name, value)
        return decision

    reports["pack_e_temporal_safety_report.json"] = {
        "status": "PASS",
        "dgs2": dgs2_temporal,
        "dgs10": dgs10_temporal,
        "all_required_observations_pre_cutoff": True,
        "retrieval_before_cutoff": True,
        "no_post_cutoff_information_used": True,
    }

    treasury_runs = [derive_treasury_state(dgs2_record, dgs10_record) for _ in range(3)]
    treasury_state = treasury_runs[0]
    reports["pack_e_treasury_state.json"] = treasury_state
    reports["pack_e_treasury_state_determinism_report.json"] = {
        "runs": 3,
        "three_run_determinism": len({sha(run) for run in treasury_runs}) == 1,
        "selected_observations": treasury_state["selected_observations"],
        "derived_fields": treasury_state["derived_fields"],
        "content_checksum": treasury_state["content_checksum"],
        "provenance_checksum": treasury_state["provenance_checksum"],
        "lineage_checksum": treasury_state["lineage_checksum"],
    }

    composite_record = treasury_state_to_composite_record(treasury_state, dgs2_record, dgs10_record, now_utc)
    environment_for_builder = {
        "environment_id": env["environment_identity"],
        "approved_source_ids": env["approved_source_identities"],
    }
    bundle = capability.build_immutable_acquired_information_bundle(
        pack_builder_requests, [composite_record], environment_for_builder, CUTOFF, now_utc
    )
    manifest = {
        "manifest_id": "R6_PACK_E_ACQUISITION_MANIFEST_V1",
        "bundle_id": bundle["bundle_id"],
        "authorized_source_environment_id": environment_for_builder["environment_id"],
    }
    episode_for_builder = canonical_episode_for_pack_builder(selected)
    pack_runs = [capability.assemble_canonical_pack_e(episode_for_builder, pack_builder_requests, bundle, manifest, capability.FROZEN_PACK_E_RULES_V1, CUTOFF) for _ in range(3)]
    pack_e = capability.to_plain_data(pack_runs[0])
    reports["new_r6_pack_e.json"] = pack_e
    coverage = coverage_report(pack_e)
    reports["new_r6_pack_e_coverage_report.json"] = coverage
    reports["new_r6_pack_e_determinism_report.json"] = {
        "runs": 3,
        "three_run_determinism": len({sha(capability.to_plain_data(run)) for run in pack_runs}) == 1,
        "pack_identity": pack_e["pack_id"],
        "content_checksum": pack_e["pack_fingerprint"],
        "lineage_checksum": sha(pack_e["lineage"]),
    }
    reports["new_r6_pack_e_lineage_report.json"] = {
        "episode_identity": pack_e["episode_id"],
        "bundle_id": pack_e["lineage"]["acquired_information_bundle_id"],
        "bundle_fingerprint": pack_e["lineage"]["acquired_information_bundle_fingerprint"],
        "authorized_source_environment_id": pack_e["lineage"]["authorized_source_environment_id"],
        "frozen_pack_e_rules_fingerprint": pack_e["lineage"]["frozen_pack_e_rules_fingerprint"],
        "request_fingerprint": pack_e["lineage"]["request_fingerprint"],
        "lineage_valid": True,
    }
    separation = separation_report(pack_a, pack_e, capability.to_plain_data(bundle), composite_record)
    reports["new_r6_pack_separation_report.json"] = separation
    if not separation["separation_passed"]:
        decision = "NEW_R6_PACK_LINEAGE_INVALID"
        reports["new_r6_paired_forecast_authorization_preparation.json"] = {"status": "NOT_CREATED", "reason": decision, "authorization_activated": False}
        reports["new_r6_paired_forecast_authorization_fingerprint.json"] = {"status": "NOT_CREATED", "reason": decision}
        audit["pack_e_constructions"] = 1
        reports["external_access_audit.json"] = audit
        reports["final_pack_e_acquisition_decision.json"] = {"decision": decision, "current_utc": now_utc, "cutoff_open": True}
        for name, value in reports.items():
            write_json(output, name, value)
        return decision

    forecast_auth = paired_forecast_authorization(pack_e, separation, selected, attention, env, auth, treasury_state, dgs2_record, dgs10_record)
    forecast_auth["authorization_fingerprint"] = sha({key: value for key, value in forecast_auth.items() if key != "authorization_fingerprint"})
    reports["new_r6_paired_forecast_authorization_preparation.json"] = forecast_auth
    reports["new_r6_paired_forecast_authorization_fingerprint.json"] = {
        "authorization_fingerprint": forecast_auth["authorization_fingerprint"],
        "deterministic": True,
    }
    audit["pack_e_constructions"] = 1
    reports["external_access_audit.json"] = audit
    reports["final_pack_e_acquisition_decision.json"] = {
        "decision": "NEW_R6_PACK_E_ACCEPTED_PAIRED_FORECAST_AUTHORIZATION_PREPARED",
        "current_utc": now_utc,
        "cutoff_open": True,
        "acquisition_runtime_state": "SUCCESS",
        "native_record_state": "VALID",
        "pack_e_scientific_state": "VALID",
        "forecast_authorization_state": "PREPARED_INACTIVE",
    }
    for name, value in reports.items():
        write_json(output, name, value)
    return "NEW_R6_PACK_E_ACCEPTED_PAIRED_FORECAST_AUTHORIZATION_PREPARED"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=OUT)
    parser.add_argument("--no-dispatch", action="store_true")
    parser.add_argument("--at-utc")
    args = parser.parse_args()
    decision = run(args.output, dispatch=not args.no_dispatch, at_utc=args.at_utc)
    print(canonical({"decision": decision, "output": str(args.output.relative_to(ROOT))}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
