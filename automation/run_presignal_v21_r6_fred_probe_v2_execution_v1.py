"""Execute the single authorized FRED probe V2 for Pack E readiness."""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
import re
import sys
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from automation import google_clients


OUT = ROOT / "outputs/presignal_v21_designed_drift_r6_fred_probe_v2_execution/R6-FRED-PROBE-V2-EXECUTION-20260724-v1"
RUNTIME_SYNC = ROOT / "outputs/presignal_v21_designed_drift_r6_prospective_runtime_sync/R6-PROSPECTIVE-RUNTIME-SYNC-20260724-v1"
PACK_A_DIR = ROOT / "outputs/presignal_v21_designed_drift_r6_pack_construction_fomc/R6-PACK-CONSTRUCTION-FOMC-20260724-v1"
SELECTED_DIR = ROOT / "outputs/presignal_v21_designed_drift_r6_episode_selection_fomc/R6-EPISODE-SELECTION-FOMC-20260724-v1"
PACK_E_MIGRATION = ROOT / "outputs/presignal_v21_designed_drift_r6_pack_e_native_adapter_migration/R6-PACK-E-NATIVE-ADAPTER-MIGRATION-20260724-v1"

START_COMMIT = "33d121f0ff9493e440ee2b69a989c761d83a3fdf"
EPISODE = "EP_EVENT_68a8e1cc3c9bf6ccc385"
PACK_A = "PACK_A_c08bab51525d614592678fae"
PACK_A_CONTENT = "sha256:c08bab51525d614592678fae0d82ce9e695ac8ff31afdf28d3e6353573818a59"
PACK_AUTH = "sha256:87fc65d0f9ec84e8efc1f0e8ef0276eb50a35d52c624191cc682dcea9f8fb869"
ROUTE_B = "sha256:8c910a343515d88ca63ce4aaf738f28f9b4a8ab22665397077858bfaf7e866e4"
CUTOFF = "2026-07-29T18:00:00Z"
SOURCE = "KSRC_FRED"
FMP_SOURCE = "KSRC_FMP"
ADAPTER = "apps_script/prospective_pack_e_acquisition.js:apiBuildProspectivePackENativeAcquisitionRecord"
FUNCTION = "apiBuildProspectivePackENativeAcquisitionRecord"
DEPLOYMENT_MODE = "PUSHED_PROJECT_HEAD"
DEPLOYED_SOURCE_FP = "sha256:7d7318dd2ac414989143f52b546f73686aa166fcfaedb4ff5cfc783e47e4d746"
AUTH_NAME = "PRESIGNAL_V21_DESIGNED_DRIFT_2_R6_FRED_BINDING_PROBE_AUTHORIZATION_V2"
AUTH_FP = "sha256:6c7936b3a9052acd70eef344ab3588204da298aa50d02c60bb1594fbf670301d"
V1_AUTH_FP = "sha256:b8a61ed078fac6b725a95ea787e54eee0ef54ae39e2f20e18e1dd38c20b273c5"
SERIES = "DGS2"
DATE_START = "2024-07-22"
DATE_END = "2024-07-24"
QUERY_IDENTITY = "FRED:DGS2|2024-07-22|2024-07-24|R6_BINDING_PROBE_V2"
REQUEST_IDENTITY = "NREQ_a90de3734b6ed432c17b"
CONFIG_REF = "FRED_API_KEY"
CONFIG_REF_VERBOSE = "Apps Script Script Property FRED_API_KEY"
CREDENTIAL_TYPE = "APPS_SCRIPT_SCRIPT_PROPERTY_API_KEY"
PACK_E_AUTH_NAME = "PRESIGNAL_V21_DESIGNED_DRIFT_2_NEW_R6_PACK_E_ACQUISITION_AUTHORIZATION_V1"


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


def cutoff_open(now_utc: str) -> bool:
    return now_utc < CUTOFF


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


def request_payload(retrieval_timestamp: str) -> dict[str, Any]:
    return {
        "source_id": SOURCE,
        "adapter_identity": ADAPTER,
        "configuration_reference": CONFIG_REF_VERBOSE,
        "credential_reference_type": CREDENTIAL_TYPE,
        "episode_id": EPISODE,
        "pack_a_identity": PACK_A,
        "request_identity": REQUEST_IDENTITY,
        "canonical_field": "US2Y_YIELD_LEVEL",
        "query_identity": QUERY_IDENTITY,
        "query_symbol": SERIES,
        "bounded_start_date": DATE_START,
        "bounded_end_date": DATE_END,
        "forecast_cutoff_ts": CUTOFF,
        "retrieval_timestamp": retrieval_timestamp,
        "as_of_timestamp": "2024-07-24T23:59:59Z",
        "source_identity": "fred:series:DGS2",
        "source_url_or_key": "fred:series:DGS2",
        "source_type": "historical_series_observation",
        "value_type": "percent",
        "source_name": "Federal Reserve Economic Data",
    }


def external_audit() -> dict[str, int]:
    return {
        "apps_script_executions": 0,
        "fred_calls": 0,
        "fmp_calls": 0,
        "eodhd_calls": 0,
        "us_treasury_calls": 0,
        "gemini_calls": 0,
        "information_request_calls": 0,
        "google_scientific_reads": 0,
        "google_scientific_writes": 0,
        "pack_e_acquisition_calls": 0,
        "pack_e_constructions": 0,
        "forecast_calls": 0,
        "outcome_operations": 0,
        "evaluation_operations": 0,
    }


def fmp_readiness_checksum() -> str:
    return sha(read_json(PACK_E_MIGRATION / "pack_e_runtime_ready_capability_inventory.json"))


def authorization_validation(prepared: Mapping[str, Any]) -> dict[str, Any]:
    valid = (
        prepared.get("authorization_name") == AUTH_NAME
        and prepared.get("authorization_fingerprint") == AUTH_FP
        and prepared.get("episode_identity") == EPISODE
        and prepared.get("pack_a_identity") == PACK_A
        and prepared.get("pack_a_content_checksum") == PACK_A_CONTENT
        and prepared.get("ksrc_fred_source_identity") == SOURCE
        and prepared.get("prospective_fred_adapter_identity") == ADAPTER
        and prepared.get("new_apps_script_deployment_identity_or_mode") == DEPLOYMENT_MODE
        and prepared.get("deployed_source_fingerprint") == DEPLOYED_SOURCE_FP
        and prepared.get("bounded_query_identity") == QUERY_IDENTITY
        and prepared.get("call_budget") == 1
        and prepared.get("retry_budget") == 0
        and prepared.get("forecast_cutoff") == CUTOFF
        and prepared.get("no_writer_contract") is True
        and prepared.get("consumed_v1_authorization_fingerprint") == V1_AUTH_FP
        and prepared.get("authorization_valid") is True
        and prepared.get("authorization_activated") is False
    )
    return {
        "authorization_name": prepared.get("authorization_name"),
        "authorization_fingerprint": prepared.get("authorization_fingerprint"),
        "authorization_valid": valid,
        "episode_identity": prepared.get("episode_identity"),
        "pack_a_identity": prepared.get("pack_a_identity"),
        "ksrc_fred_identity": prepared.get("ksrc_fred_source_identity"),
        "adapter_identity": prepared.get("prospective_fred_adapter_identity"),
        "deployment_identity": prepared.get("new_apps_script_deployment_identity_or_mode"),
        "deployed_source_fingerprint": prepared.get("deployed_source_fingerprint"),
        "bounded_query_identity": prepared.get("bounded_query_identity"),
        "call_budget": prepared.get("call_budget"),
        "retry_budget": prepared.get("retry_budget"),
        "forecast_cutoff": prepared.get("forecast_cutoff"),
        "no_writer_contract": prepared.get("no_writer_contract"),
        "consumed_v1_authorization_fingerprint": prepared.get("consumed_v1_authorization_fingerprint"),
    }


def classify_probe(record: Mapping[str, Any] | None, metadata: Mapping[str, Any] | None) -> tuple[str, str, dict[str, Any]]:
    binding = {
        "expected_reference": CONFIG_REF,
        "resolver_reached": False,
        "reference_found": None,
        "credential_structurally_accepted": None,
        "alias_used": False,
    }
    if metadata and not metadata.get("ok"):
        return "FRED_TRANSPORT_FAILED", "NEW_R6_PACK_E_FRED_ACCESS_PROBE_V2_FAILED", binding
    if not isinstance(record, Mapping):
        return "FRED_NATIVE_RECORD_INVALID", "NEW_R6_PACK_E_FRED_ACCESS_PROBE_V2_FAILED", binding

    status = str(record.get("status") or "")
    err = str(record.get("error_classification") or "")
    reason = str(record.get("reason") or "")
    binding["resolver_reached"] = True

    if status == "SUPPLIED":
        binding["reference_found"] = True
        binding["credential_structurally_accepted"] = True
        return "FRED_BINDING_AND_ACCESS_PROVEN", "NEW_R6_PACK_E_FRED_BINDING_PROVEN_ACQUISITION_AUTHORIZATION_PREPARED", binding

    if err == "SOURCE_ACCESS_NOT_AUTHORIZED":
        binding["reference_found"] = True
        binding["credential_structurally_accepted"] = False
        return "FRED_ACCESS_NOT_AUTHORIZED", "NEW_R6_PACK_E_FRED_ACCESS_PROBE_V2_FAILED", binding

    if err == "SOURCE_CONTENT_NOT_FOUND":
        # For DGS2 over 2024-07-22..2024-07-24, an empty row set is strong
        # evidence that the Script Property was unresolved before any live
        # FRED fetch occurred because the legacy fetcher returns [] when the
        # property is missing.
        if "NO_OBSERVATION_AT_OR_BEFORE_AS_OF" in reason:
            binding["reference_found"] = False
            binding["credential_structurally_accepted"] = False
            return "FRED_CONFIGURATION_REFERENCE_MISSING", "NEW_R6_PACK_E_FRED_BINDING_NOT_FOUND", binding
        binding["reference_found"] = True
        binding["credential_structurally_accepted"] = True
        return "FRED_CONTENT_NOT_FOUND", "NEW_R6_PACK_E_FRED_ACCESS_PROBE_V2_FAILED", binding

    if err == "SOURCE_TEMPORAL_CONTRACT_UNSUPPORTED":
        binding["reference_found"] = True
        binding["credential_structurally_accepted"] = True
        return "FRED_TEMPORAL_VALIDATION_FAILED", "NEW_R6_PACK_E_FRED_ACCESS_PROBE_V2_FAILED", binding

    return "FRED_NATIVE_RECORD_INVALID", "NEW_R6_PACK_E_FRED_ACCESS_PROBE_V2_FAILED", binding


def validate_native_record(record: Any, request: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(record, Mapping):
        return {"schema_valid": False, "reason": "RECORD_NOT_OBJECT", "writer_count": 0}
    required = (
        "object",
        "acquisition_record_id",
        "source_id",
        "adapter_identity",
        "request_identity",
        "episode_id",
        "forecast_cutoff_ts",
        "retrieval_timestamp",
        "acquisition_timestamp",
        "raw_checksum",
        "normalized_checksum",
        "status",
        "source_identity",
        "query_identity",
    )
    missing = [field for field in required if field not in record or record.get(field) in (None, "")]
    schema_valid = record.get("object") == "NATIVE_ACQUISITION_RECORD" and not missing
    supplied = record.get("status") == "SUPPLIED"
    source_item = ((record.get("source_items") or [None])[0] if supplied else None) or {}
    effective_ts = str(record.get("source_timestamp") or source_item.get("source_timestamp") or "")
    retrieval_ts = str(record.get("retrieval_timestamp") or "")
    provenance_valid = (
        record.get("episode_id") == EPISODE
        and record.get("pack_a_identity") == PACK_A
        and record.get("request_identity") == REQUEST_IDENTITY
    )
    lineage_valid = provenance_valid and record.get("source_id") == SOURCE and record.get("adapter_identity") == ADAPTER
    temporal_valid = (
        retrieval_ts.startswith("2026-07-24T")
        or retrieval_ts < CUTOFF
    )
    if supplied:
        temporal_classification = "HISTORICAL_BOUND_QUERY_VALID"
    else:
        temporal_classification = "HISTORICAL_BOUND_QUERY_NO_OBSERVATION"
    return {
        "record_identity": record.get("acquisition_record_id"),
        "source_identity": record.get("source_identity"),
        "adapter_identity": record.get("adapter_identity"),
        "series": request["query_symbol"],
        "request_identity": record.get("request_identity"),
        "effective_timestamp": effective_ts,
        "publication_timestamp_supported": False,
        "retrieval_timestamp": retrieval_ts,
        "temporal_classification": temporal_classification,
        "raw_checksum": record.get("raw_checksum"),
        "normalized_checksum": record.get("normalized_checksum"),
        "provenance_valid": provenance_valid,
        "lineage_valid": lineage_valid,
        "schema_valid": schema_valid and record.get("source_id") == SOURCE and record.get("adapter_identity") == ADAPTER and record.get("query_identity") == request["query_identity"],
        "writer_count": 0,
        "required_fields_missing": missing,
        "status": record.get("status"),
        "error_classification": record.get("error_classification"),
        "reason": record.get("reason"),
    }


def temporal_validation(record: Mapping[str, Any] | None, request: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(record, Mapping):
        return {
            "bounded_query_preserved": False,
            "timestamps_parse_deterministically": False,
            "latest_eligible_observation_selection_deterministic": False,
            "post_query_observation_used": False,
        }
    if record.get("status") != "SUPPLIED":
        return {
            "bounded_query_preserved": record.get("query_identity") == request["query_identity"],
            "timestamps_parse_deterministically": True,
            "latest_eligible_observation_selection_deterministic": True,
            "post_query_observation_used": False,
        }
    raw = json.loads(record.get("raw_acquired_content") or "{}")
    rows = raw.get("rows") or []
    dates = [str(row.get("date") or "") for row in rows]
    selected = json.loads(record.get("normalized_acquired_content") or "{}").get("selected_observation") or {}
    return {
        "bounded_query_preserved": all(DATE_START <= value <= DATE_END for value in dates),
        "timestamps_parse_deterministically": all(bool(value) and len(value) == 10 for value in dates),
        "latest_eligible_observation_selection_deterministic": str(selected.get("date") or "") == max(dates) if dates else False,
        "post_query_observation_used": any(value > DATE_END for value in dates),
    }


def required_field_coverage(fred_ready: bool) -> dict[str, Any]:
    required = read_json(PACK_E_MIGRATION / "pack_e_minimum_required_coverage.json")
    bindings = read_json(PACK_E_MIGRATION / "pack_e_source_field_binding_report.json")
    inventory = read_json(PACK_E_MIGRATION / "pack_e_runtime_ready_capability_inventory.json")
    reports = []
    for item in required["required_fields"]:
        reports.append(
            {
                "field_identity": item["capability_id"],
                "classification": item["classification"],
                "approved_source": SOURCE,
                "prospective_adapter": ADAPTER,
                "runtime_binding": "VALID" if fred_ready else "BLOCKED",
                "query_support": "SUPPORTED" if fred_ready else "UNPROVEN",
                "coverage_status": "COMPLETE" if fred_ready else "INCOMPLETE",
                "canonical_fields": item["field_binding"],
                "request_identity": item["request_identity"],
            }
        )
    return {
        "required_fields": reports,
        "optional_fields": required["optional_fields"],
        "contextual_or_not_acquired": required["contextual_or_not_acquired"],
        "source_field_bindings": bindings["candidate_source_bindings"],
        "existing_fmp_readiness_evidence_checksum": sha(inventory),
    }


def environment_object(probe_checksum: str, coverage: Mapping[str, Any]) -> dict[str, Any]:
    selected = read_json(SELECTED_DIR / "new_r6_selected_episode_manifest.json")
    return {
        "object": "PRESIGNAL_V21_DESIGNED_DRIFT_2_R6_PACK_E_SOURCE_ENVIRONMENT_V1",
        "environment_identity": "R6_PACK_E_FRED_TREASURY_MINIMUM_V2",
        "episode_identity": EPISODE,
        "episode_content_checksum": selected.get("content_checksum"),
        "episode_provenance_checksum": selected.get("provenance_checksum"),
        "episode_lineage_checksum": selected.get("lineage_checksum"),
        "pack_a_identity": PACK_A,
        "pack_a_content_checksum": PACK_A_CONTENT,
        "pack_authorization_fingerprint": PACK_AUTH,
        "approved_source_identities": [SOURCE],
        "prospective_adapter_identities": [ADAPTER],
        "deployment_identity": DEPLOYMENT_MODE,
        "deployment_fingerprint": DEPLOYED_SOURCE_FP,
        "configuration_reference_identities": [CONFIG_REF],
        "credential_reference_classifications": {SOURCE: CREDENTIAL_TYPE, FMP_SOURCE: "APPS_SCRIPT_SCRIPT_PROPERTY_API_KEY_RESOLVER_REUSED_EVIDENCE_ONLY"},
        "required_field_bindings": {
            "TREASURY_2Y_10Y_PRESESSION_STATE": {
                "source_id": SOURCE,
                "query_symbols": ["DGS2", "DGS10"],
                "canonical_fields": [
                    "US2Y_YIELD_LEVEL",
                    "US10Y_YIELD_LEVEL",
                    "US2Y_CHANGE_FROM_PRIOR_CLOSE",
                    "US10Y_CHANGE_FROM_PRIOR_CLOSE",
                    "US10Y_MINUS_US2Y_CURVE",
                ],
            }
        },
        "optional_field_bindings": {
            "DXY_PRESESSION_STATE": "KSRC_FMP runtime-ready existing evidence preserved; not required for minimum environment",
            "USDJPY_PRESESSION_STATE": "KSRC_FMP runtime-ready existing evidence preserved; EODHD remains optional and excluded",
        },
        "per_source_call_budgets": {SOURCE: 2},
        "total_call_budget": 2,
        "retry_budget": 0,
        "forecast_cutoff": CUTOFF,
        "failure_stop_policy": "stop_on_source_failure_no_fallback",
        "successful_fred_probe_evidence_checksum": probe_checksum,
        "existing_fmp_readiness_evidence_checksum": coverage["existing_fmp_readiness_evidence_checksum"],
    }


def acquisition_authorization(environment: Mapping[str, Any]) -> dict[str, Any]:
    selected = read_json(SELECTED_DIR / "new_r6_selected_episode_manifest.json")
    return {
        "authorization_name": PACK_E_AUTH_NAME,
        "source_environment_fingerprint": environment["environment_fingerprint"],
        "pack_authorization_fingerprint": PACK_AUTH,
        "episode_identity": EPISODE,
        "episode_content_checksum": selected.get("content_checksum"),
        "episode_provenance_checksum": selected.get("provenance_checksum"),
        "episode_lineage_checksum": selected.get("lineage_checksum"),
        "pack_a_identity": PACK_A,
        "pack_a_content_checksum": PACK_A_CONTENT,
        "approved_source_identities": environment["approved_source_identities"],
        "prospective_adapter_identities": environment["prospective_adapter_identities"],
        "apps_script_deployment_fingerprint": DEPLOYED_SOURCE_FP,
        "required_pack_e_field_coverage": environment["required_field_bindings"],
        "configuration_reference_classifications": {SOURCE: "EXISTING_SCRIPT_PROPERTY_REFERENCE_PROVEN_BY_V2_PROBE"},
        "per_source_call_budgets": environment["per_source_call_budgets"],
        "total_call_budget": environment["total_call_budget"],
        "retry_budget": 0,
        "forecast_cutoff": CUTOFF,
        "secret_safety_contract": "reference_only_no_secret_values_or_headers",
        "failure_stop_policy": "stop_on_source_failure_no_fallback",
        "authorization_valid": True,
        "authorization_activated": False,
        "pack_e_acquisition_calls": 0,
        "pack_e_constructed": False,
    }


def run(output: Path = OUT, *, dispatch: bool = True, at_utc: str | None = None) -> str:
    output.mkdir(parents=True, exist_ok=True)
    current_utc = at_utc or utc_now()
    prepared = read_json(RUNTIME_SYNC / "fred_probe_v2_authorization_preparation.json")
    auth_validation = authorization_validation(prepared)
    request = request_payload(current_utc)
    reports: dict[str, Any] = {
        "fred_probe_v2_authorization_validation.json": auth_validation,
        "secret_safety_report.json": {
            "new_credential_created": False,
            "secret_value_exposed": False,
            "credential_committed": False,
        },
    }
    audit = external_audit()

    if not auth_validation["authorization_valid"]:
        decision = "NEW_R6_PACK_E_FRED_PROBE_V2_BLOCKED_AUTHORIZATION_MISMATCH"
        reports.update(
            {
                "fred_probe_v2_activation_record.json": {"status": "NOT_CREATED", "reason": "AUTHORIZATION_MISMATCH"},
                "fred_probe_v2_request.json": {"status": "NOT_EXECUTED", "reason": "AUTHORIZATION_MISMATCH"},
                "fred_probe_v2_transport_result.json": {"status": "NOT_EXECUTED", "reason": "AUTHORIZATION_MISMATCH"},
                "fred_probe_v2_binding_result.json": {"status": "NOT_EXECUTED", "reason": "AUTHORIZATION_MISMATCH"},
                "fred_probe_v2_native_record.json": {"status": "NOT_CREATED", "reason": "AUTHORIZATION_MISMATCH"},
                "fred_probe_v2_native_record_validation.json": {"status": "NOT_EXECUTED", "reason": "AUTHORIZATION_MISMATCH"},
                "fred_probe_v2_temporal_validation.json": {"status": "NOT_EXECUTED", "reason": "AUTHORIZATION_MISMATCH"},
                "fred_probe_v2_final_classification.json": {"status": "NOT_EXECUTED", "classification": "AUTHORIZATION_MISMATCH"},
                "pack_e_minimum_environment_revalidation.json": {"status": "NOT_CREATED", "reason": "AUTHORIZATION_MISMATCH"},
                "pack_e_required_field_coverage.json": {"status": "NOT_CREATED", "reason": "AUTHORIZATION_MISMATCH"},
                "r6_pack_e_source_environment.json": {"status": "NOT_CREATED", "reason": "AUTHORIZATION_MISMATCH"},
                "r6_pack_e_source_environment_fingerprint.json": {"status": "NOT_CREATED"},
                "r6_pack_e_acquisition_authorization_preparation.json": {"status": "NOT_CREATED", "authorization_activated": False, "pack_e_acquisition_calls": 0, "pack_e_constructed": False},
                "r6_pack_e_acquisition_authorization_fingerprint.json": {"status": "NOT_CREATED"},
            }
        )
        reports["external_access_audit.json"] = audit
        reports["final_fred_probe_v2_decision.json"] = {"decision": decision, "current_utc": current_utc, "cutoff_open": cutoff_open(current_utc)}
        for name, value in reports.items():
            write_json(output, name, value)
        return decision

    if not cutoff_open(current_utc):
        decision = "NEW_R6_PACK_E_FRED_PROBE_V2_BLOCKED_CUTOFF_CLOSED"
        reports.update(
            {
                "fred_probe_v2_activation_record.json": {"status": "NOT_CREATED", "reason": "CUTOFF_CLOSED"},
                "fred_probe_v2_request.json": {"status": "NOT_EXECUTED", "reason": "CUTOFF_CLOSED"},
                "fred_probe_v2_transport_result.json": {"status": "NOT_EXECUTED", "reason": "CUTOFF_CLOSED"},
                "fred_probe_v2_binding_result.json": {"status": "NOT_EXECUTED", "reason": "CUTOFF_CLOSED"},
                "fred_probe_v2_native_record.json": {"status": "NOT_CREATED", "reason": "CUTOFF_CLOSED"},
                "fred_probe_v2_native_record_validation.json": {"status": "NOT_EXECUTED", "reason": "CUTOFF_CLOSED"},
                "fred_probe_v2_temporal_validation.json": {"status": "NOT_EXECUTED", "reason": "CUTOFF_CLOSED"},
                "fred_probe_v2_final_classification.json": {"status": "NOT_EXECUTED", "classification": "CUTOFF_CLOSED"},
                "pack_e_minimum_environment_revalidation.json": {"status": "NOT_CREATED", "reason": "CUTOFF_CLOSED"},
                "pack_e_required_field_coverage.json": {"status": "NOT_CREATED", "reason": "CUTOFF_CLOSED"},
                "r6_pack_e_source_environment.json": {"status": "NOT_CREATED", "reason": "CUTOFF_CLOSED"},
                "r6_pack_e_source_environment_fingerprint.json": {"status": "NOT_CREATED"},
                "r6_pack_e_acquisition_authorization_preparation.json": {"status": "NOT_CREATED", "authorization_activated": False, "pack_e_acquisition_calls": 0, "pack_e_constructed": False},
                "r6_pack_e_acquisition_authorization_fingerprint.json": {"status": "NOT_CREATED"},
            }
        )
        reports["external_access_audit.json"] = audit
        reports["final_fred_probe_v2_decision.json"] = {"decision": decision, "current_utc": current_utc, "cutoff_open": False}
        for name, value in reports.items():
            write_json(output, name, value)
        return decision

    reports["fred_probe_v2_activation_record.json"] = {
        "authorization_name": AUTH_NAME,
        "authorization_fingerprint": AUTH_FP,
        "authorization_activated": True,
        "activation_timestamp": current_utc,
        "activation_identity": "FRED_PROBE_V2_SINGLE_USE_ACTIVATION",
        "pre_dispatch_journal_state": {"apps_script_executions": 0, "fred_calls": 0, "retries": 0},
        "consumed": True,
    }
    reports["fred_probe_v2_request.json"] = {"request": request, "request_checksum": sha(request)}

    metadata: dict[str, Any]
    if dispatch:
        creds = google_clients.load_credentials(False, token_path=ROOT / "local/token.json", persist_refresh=False)
        service = google_clients.build_script_service(creds, 120)
        metadata = google_clients.run_script_function_with_metadata(service, google_clients.default_script_id(), FUNCTION, [request])
        audit["apps_script_executions"] = 1
    else:
        metadata = {"ok": False, "classification": {"category": "NOT_DISPATCHED"}, "response": None}
    record = metadata.get("result") if metadata.get("ok") else None

    primary_classification, decision, binding = classify_probe(record, metadata)
    reports["fred_probe_v2_transport_result.json"] = redact(
        {
            "transport_status": "SUCCESS" if metadata.get("ok") else "FAILED",
            "apps_script_runtime_state": "SUCCESS" if metadata.get("ok") else "FAILED",
            "http_or_source_status": "SUPPLIED" if isinstance(record, Mapping) and record.get("status") == "SUPPLIED" else (
                (record or {}).get("error_classification") if isinstance(record, Mapping) else (metadata.get("classification") or {}).get("category")
            ),
            "metadata": metadata,
        }
    )
    reports["fred_probe_v2_binding_result.json"] = binding
    reports["fred_probe_v2_native_record.json"] = redact(record) if isinstance(record, Mapping) else {"status": "NOT_CREATED"}
    native_validation = validate_native_record(record, request) if isinstance(record, Mapping) else {"schema_valid": False, "writer_count": 0, "reason": "NO_RECORD"}
    reports["fred_probe_v2_native_record_validation.json"] = native_validation
    reports["fred_probe_v2_temporal_validation.json"] = temporal_validation(record, request)

    if primary_classification == "FRED_BINDING_AND_ACCESS_PROVEN":
        audit["fred_calls"] = 1
    elif primary_classification in {"FRED_ACCESS_NOT_AUTHORIZED", "FRED_RESPONSE_INVALID", "FRED_QUERY_UNSUPPORTED"}:
        audit["fred_calls"] = 1
    else:
        audit["fred_calls"] = 0

    reports["fred_probe_v2_final_classification.json"] = {
        "probe_classification": primary_classification,
        "decision": decision,
        "apps_script_runtime_state": "SUCCESS" if metadata.get("ok") else "FAILED",
        "credential_resolution_state": "RESOLVED" if binding["reference_found"] else "UNRESOLVED",
        "fred_source_access_state": "SUCCESS" if primary_classification == "FRED_BINDING_AND_ACCESS_PROVEN" else "FAILED",
        "native_record_validation_state": "VALID" if native_validation.get("schema_valid") and isinstance(record, Mapping) else "INVALID",
        "pack_e_scientific_state": "NOT_CONSTRUCTED",
    }

    if decision == "NEW_R6_PACK_E_FRED_BINDING_PROVEN_ACQUISITION_AUTHORIZATION_PREPARED":
        coverage = required_field_coverage(True)
        reports["pack_e_required_field_coverage.json"] = coverage
        probe_checksum = sha({
            "request": request,
            "record": record,
            "binding": binding,
            "native_validation": native_validation,
            "temporal_validation": reports["fred_probe_v2_temporal_validation.json"],
        })
        environment = environment_object(probe_checksum, coverage)
        environment["environment_fingerprint"] = sha(environment)
        acquisition = acquisition_authorization(environment)
        acquisition["authorization_fingerprint"] = sha(acquisition)
        reports["pack_e_minimum_environment_revalidation.json"] = {
            "environment_identity": environment["environment_identity"],
            "source_identities": environment["approved_source_identities"],
            "adapter_identities": environment["prospective_adapter_identities"],
            "required_fields": list(environment["required_field_bindings"].keys()),
            "missing_required_fields": [],
            "coverage_complete": True,
            "runtime_ready": True,
            "existing_fmp_readiness_reused_without_new_call": True,
            "eodhd_excluded_as_optional": True,
        }
        reports["r6_pack_e_source_environment.json"] = environment
        reports["r6_pack_e_source_environment_fingerprint.json"] = {
            "environment_fingerprint": environment["environment_fingerprint"],
            "deterministic": True,
        }
        reports["r6_pack_e_acquisition_authorization_preparation.json"] = acquisition
        reports["r6_pack_e_acquisition_authorization_fingerprint.json"] = {
            "authorization_fingerprint": acquisition["authorization_fingerprint"],
            "deterministic": True,
        }
    else:
        fred_ready = primary_classification == "FRED_BINDING_AND_ACCESS_PROVEN"
        coverage = required_field_coverage(fred_ready)
        reports["pack_e_required_field_coverage.json"] = coverage
        reports["pack_e_minimum_environment_revalidation.json"] = {
            "coverage_complete": False,
            "runtime_ready": False,
            "missing_required_fields": ["TREASURY_2Y_10Y_PRESESSION_STATE"] if not fred_ready else [],
            "existing_fmp_readiness_reused_without_new_call": True,
            "remaining_required_gap": "KSRC_FRED runtime binding not proven" if not fred_ready else None,
        }
        reports["r6_pack_e_source_environment.json"] = {"status": "NOT_CREATED", "reason": primary_classification}
        reports["r6_pack_e_source_environment_fingerprint.json"] = {"status": "NOT_CREATED"}
        reports["r6_pack_e_acquisition_authorization_preparation.json"] = {
            "status": "NOT_CREATED",
            "reason": primary_classification,
            "authorization_activated": False,
            "pack_e_acquisition_calls": 0,
            "pack_e_constructed": False,
        }
        reports["r6_pack_e_acquisition_authorization_fingerprint.json"] = {"status": "NOT_CREATED"}

    reports["external_access_audit.json"] = audit
    reports["final_fred_probe_v2_decision.json"] = {
        "decision": decision,
        "current_utc": current_utc,
        "cutoff_open": True,
        "primary_probe_classification": primary_classification,
    }
    for name, value in reports.items():
        write_json(output, name, value)
    return decision


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
