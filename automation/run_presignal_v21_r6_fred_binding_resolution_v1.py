"""One-use FRED binding probe for the selected prospective R6 Pack E route.

The sole external action is an explicitly authorized, bounded DGS2 read via
the existing Apps Script prospective adapter.  It is connectivity/contract
evidence, never Pack E acquisition evidence.
"""
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


PACK = ROOT / "outputs/presignal_v21_designed_drift_r6_pack_construction_fomc/R6-PACK-CONSTRUCTION-FOMC-20260724-v1"
PRIORITY = ROOT / "outputs/presignal_v21_designed_drift_r6_information_request_priority_contract_repair/R6-INFORMATION-REQUEST-PRIORITY-CONTRACT-REPAIR-20260724-v1"
SELECTED = ROOT / "outputs/presignal_v21_designed_drift_r6_episode_selection_fomc/R6-EPISODE-SELECTION-FOMC-20260724-v1"
OUT = ROOT / "outputs/presignal_v21_designed_drift_r6_fred_binding_resolution/R6-FRED-BINDING-RESOLUTION-20260724-v1"

EPISODE = "EP_EVENT_68a8e1cc3c9bf6ccc385"
PACK_A = "PACK_A_c08bab51525d614592678fae"
PACK_AUTH = "sha256:87fc65d0f9ec84e8efc1f0e8ef0276eb50a35d52c624191cc682dcea9f8fb869"
ROUTE_B = "sha256:8c910a343515d88ca63ce4aaf738f28f9b4a8ab22665397077858bfaf7e866e4"
CUTOFF = "2026-07-29T18:00:00Z"
SOURCE = "KSRC_FRED"
ADAPTER = "apps_script/prospective_pack_e_acquisition.js:apiBuildProspectivePackENativeAcquisitionRecord"
FUNCTION = "apiBuildProspectivePackENativeAcquisitionRecord"
CONFIG = "Apps Script Script Property FRED_API_KEY"
CREDENTIAL_TYPE = "APPS_SCRIPT_SCRIPT_PROPERTY_API_KEY"
AUTH_NAME = "PRESIGNAL_V21_DESIGNED_DRIFT_2_R6_FRED_BINDING_PROBE_AUTHORIZATION_V1"


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def read(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write(output: Path, name: str, value: Any) -> None:
    output.mkdir(parents=True, exist_ok=True)
    (output / name).write_text(canonical(value) + "\n", encoding="utf-8")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def cutoff_open(timestamp: str) -> bool:
    return timestamp < CUTOFF


def redact(value: Any) -> Any:
    """Retain only evidence, never a token/header/query credential value."""
    if isinstance(value, Mapping):
        sensitive = re.compile(r"^(access_token|refresh_token|id_token|client_secret|api[_-]?key|authorization_header|cookie)$", re.I)
        return {str(key): redact("REDACTED" if sensitive.search(str(key)) else item) for key, item in value.items()}
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, str):
        value = re.sub(r"(?i)(api[_-]?key=)[^&\s]+", r"\1REDACTED", value)
        value = re.sub(r"(?i)(authorization:\s*)[^\s]+", r"\1REDACTED", value)
    return value


def probe_request(retrieval_timestamp: str) -> dict[str, Any]:
    return {
        "source_id": SOURCE,
        "adapter_identity": ADAPTER,
        "configuration_reference": CONFIG,
        "credential_reference_type": CREDENTIAL_TYPE,
        "episode_id": EPISODE,
        "pack_a_identity": PACK_A,
        "request_identity": "NREQ_a90de3734b6ed432c17b",
        "canonical_field": "US2Y_YIELD_LEVEL",
        "query_identity": "FRED:DGS2|2024-07-22|2024-07-24|R6_BINDING_PROBE_V1",
        "query_symbol": "DGS2",
        "bounded_start_date": "2024-07-22",
        "bounded_end_date": "2024-07-24",
        "forecast_cutoff_ts": CUTOFF,
        "retrieval_timestamp": retrieval_timestamp,
        "as_of_timestamp": "2024-07-24T23:59:59Z",
        "source_identity": "fred:series:DGS2",
        "source_url_or_key": "fred:series:DGS2",
        "source_type": "historical_series_observation",
        "value_type": "percent",
        "source_name": "Federal Reserve Economic Data",
    }


def authorization(request: Mapping[str, Any]) -> dict[str, Any]:
    selected = read(SELECTED / "new_r6_selected_episode_manifest.json")
    pack_a = read(PACK / "new_r6_pack_a.json")
    value = {
        "authorization_name": AUTH_NAME,
        "status": "PREPARED_SINGLE_USE_NOT_ACTIVATED",
        "episode_identity": EPISODE,
        "episode_content_checksum": selected.get("content_checksum"),
        "episode_provenance_checksum": selected.get("provenance_checksum"),
        "episode_lineage_checksum": selected.get("lineage_checksum"),
        "pack_a_identity": PACK_A,
        "pack_a_content_checksum": pack_a.get("content_checksum"),
        "pack_authorization_fingerprint": PACK_AUTH,
        "source_identity": SOURCE,
        "prospective_adapter_identity": ADAPTER,
        "configuration_reference_identity": CONFIG,
        "credential_reference_type": CREDENTIAL_TYPE,
        "bounded_query_identity": request["query_identity"],
        "call_budget": 1,
        "retry_budget": 0,
        "forecast_cutoff": CUTOFF,
        "no_writer_contract": True,
        "pack_e_acquisition_calls": 0,
        "authorization_activated": False,
    }
    value["authorization_fingerprint"] = sha(value)
    return value


def validate_native_record(record: Any, request: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(record, Mapping):
        return {"valid": False, "reason": "RECORD_NOT_OBJECT", "writer_count": 0}
    required = ("object", "acquisition_record_id", "source_id", "adapter_identity", "request_identity", "episode_id", "forecast_cutoff_ts", "retrieval_timestamp", "source_timestamp", "as_of_timestamp", "raw_checksum", "normalized_checksum", "status")
    missing = [field for field in required if not record.get(field)]
    temporal = all(str(record.get(field) or "") <= CUTOFF for field in ("retrieval_timestamp", "source_timestamp", "as_of_timestamp"))
    status = str(record.get("status") or "")
    return {
        "valid": not missing and record.get("object") == "NATIVE_ACQUISITION_RECORD" and record.get("source_id") == SOURCE and record.get("adapter_identity") == ADAPTER and record.get("request_identity") == request["request_identity"] and record.get("episode_id") == EPISODE and record.get("forecast_cutoff_ts", "").startswith("2026-07-29T18:00:00") and temporal and status in {"SUPPLIED", "UNAVAILABLE"},
        "required_fields_missing": missing,
        "source_identity_valid": record.get("source_identity") == request["source_identity"],
        "adapter_identity_valid": record.get("adapter_identity") == ADAPTER,
        "query_identity_valid": record.get("query_identity") == request["query_identity"],
        "temporal_valid": temporal,
        "record_status": status,
        "raw_checksum": record.get("raw_checksum"),
        "normalized_checksum": record.get("normalized_checksum"),
        "provenance_lineage_valid": record.get("episode_id") == EPISODE and record.get("request_identity") == request["request_identity"],
        "writer_count": 0,
    }


def audit() -> dict[str, int]:
    return {"fred_probe_dispatches": 0, "fred_calls": 0, "fmp_calls": 0, "eodhd_calls": 0, "us_treasury_calls": 0, "apps_script_executions": 0, "google_reads": 0, "google_writes": 0, "gemini_calls": 0, "pack_e_acquisition_calls": 0, "pack_e_constructions": 0, "forecast_calls": 0, "outcome_operations": 0, "evaluation_operations": 0}


def run(output: Path = OUT, *, dispatch: bool = True, at_utc: str | None = None) -> str:
    timestamp = at_utc or utc_now()
    request = probe_request(timestamp)
    auth = authorization(request)
    binding_trace = {
        "configuration_convention_authority": ["apps_script/market_context_v2b.js:_v2bFetchFredHistory_", "docs/RuleBook_v1.4.md", "docs/Blueprint_v1.4.md"],
        "expected_reference": "FRED_API_KEY",
        "existing_authoritative_aliases": [],
        "resolver": "PropertiesService.getScriptProperties().getProperty('FRED_API_KEY')",
        "binding_source": "existing Apps Script Script Property through established authorized-user Execution API bridge",
        "local_binding_file_created": False,
        "secret_value_inspected": False,
    }
    reports: dict[str, Any] = {
        "fred_configuration_reference_trace.json": binding_trace,
        "fred_binding_resolution_report.json": {"expected_reference": "FRED_API_KEY", "existing_reference_found": "PENDING_PROBE", "binding_source": binding_trace["binding_source"], "binding_method": "existing resolver; no alias and no copied local secret", "alias_used": False},
        "fred_secret_safety_report.json": {"credential_created": False, "credential_contents_exposed": False, "credential_committed": False, "secret_value_hashed": False, "authorization_headers_recorded": False},
        "fred_probe_authorization.json": auth,
        "fred_probe_authorization_fingerprint.json": {"authorization_fingerprint": auth["authorization_fingerprint"], "deterministic": True},
        "fred_access_probe_request.json": {"request": request, "request_checksum": sha({key: value for key, value in request.items() if key != "retrieval_timestamp"}), "probe_is_pack_e_acquisition": False},
    }
    external = audit()
    if not cutoff_open(timestamp):
        decision = "NEW_R6_PACK_E_FRED_BINDING_BLOCKED_CUTOFF_CLOSED"
        reports.update({
            "fred_access_probe_result.json": {"status": "NOT_EXECUTED", "reason": "CUTOFF_CLOSED"},
            "fred_native_record_validation.json": {"status": "NOT_EXECUTED"},
            "pack_e_minimum_environment_revalidation.json": {"status": "NOT_CREATED", "reason": "CUTOFF_CLOSED"},
            "r6_pack_e_source_environment.json": {"status": "NOT_CREATED", "reason": "CUTOFF_CLOSED"},
            "r6_pack_e_source_environment_fingerprint.json": {"status": "NOT_CREATED"},
            "r6_pack_e_acquisition_authorization_preparation.json": {"status": "NOT_CREATED", "authorization_activated": False, "pack_e_acquisition_calls": 0, "pack_e_constructed": False},
            "r6_pack_e_acquisition_authorization_fingerprint.json": {"status": "NOT_CREATED"},
        })
    else:
        auth["authorization_activated"] = True
        auth["status"] = "ACTIVATED_FOR_SINGLE_PROBE"
        result: dict[str, Any]
        if not dispatch:
            result = {"ok": False, "classification": {"category": "NOT_DISPATCHED"}, "response": None}
        else:
            try:
                credentials = google_clients.load_credentials(False, token_path=ROOT / "local/token.json", persist_refresh=False)
                service = google_clients.build_script_service(credentials, 120)
                result = google_clients.run_script_function_with_metadata(service, google_clients.default_script_id(), FUNCTION, [request])
                external["apps_script_executions"] = 1
                external["fred_probe_dispatches"] = 1
            except Exception as exc:
                result = {"ok": False, "classification": google_clients.classify_google_exception(exc), "response": None}
                external["apps_script_executions"] = 0
        raw_result = result.get("result") if result.get("ok") else None
        validation = validate_native_record(raw_result, request) if raw_result is not None else {"valid": False, "reason": (result.get("classification") or {}).get("category", "SOURCE_ACCESS_NOT_AUTHORIZED"), "writer_count": 0}
        # A supplied record proves exactly one underlying legacy fetch.  An
        # unavailable record may have short-circuited for a missing key, so it
        # is never overstated as a confirmed FRED HTTP call.
        if validation.get("record_status") == "SUPPLIED":
            external["fred_calls"] = 1
        reports["fred_access_probe_result.json"] = redact({"probe_timestamp": timestamp, "authorization_activated": True, "transport_status": "SUCCESS" if result.get("ok") else "FAILED", "execution_status": "COMPLETED" if result.get("ok") else "NOT_COMPLETED", "metadata": result if not result.get("ok") else {"elapsed_ms": result.get("elapsed_ms"), "classification": result.get("classification")}, "record": raw_result, "probe_is_pack_e_acquisition": False})
        reports["fred_native_record_validation.json"] = validation
        if not result.get("ok"):
            decision = "NEW_R6_PACK_E_FRED_ACCESS_PROBE_FAILED"
            reports["fred_binding_resolution_report.json"]["existing_reference_found"] = "UNPROVEN_PROBE_FAILED"
            failure_reason = (result.get("classification") or {}).get("category", "SOURCE_ACCESS_NOT_AUTHORIZED")
            reports.update({
                "pack_e_minimum_environment_revalidation.json": {"status": "NOT_CREATED", "reason": failure_reason},
                "r6_pack_e_source_environment.json": {"status": "NOT_CREATED", "reason": failure_reason},
                "r6_pack_e_source_environment_fingerprint.json": {"status": "NOT_CREATED", "reason": failure_reason},
                "r6_pack_e_acquisition_authorization_preparation.json": {"status": "NOT_CREATED", "reason": failure_reason, "authorization_activated": False, "pack_e_acquisition_calls": 0, "pack_e_constructed": False},
                "r6_pack_e_acquisition_authorization_fingerprint.json": {"status": "NOT_CREATED", "reason": failure_reason},
            })
        elif not validation["valid"] or validation["record_status"] != "SUPPLIED":
            decision = "NEW_R6_PACK_E_FRED_ACCESS_PROBE_FAILED"
            reports["fred_binding_resolution_report.json"]["existing_reference_found"] = "RESOLVER_REACHED_BUT_RECORD_NOT_VALID"
            reports.update({
                "pack_e_minimum_environment_revalidation.json": {"status": "NOT_CREATED", "reason": validation.get("reason") or validation.get("record_status")},
                "r6_pack_e_source_environment.json": {"status": "NOT_CREATED", "reason": validation.get("reason") or validation.get("record_status")},
                "r6_pack_e_source_environment_fingerprint.json": {"status": "NOT_CREATED"},
                "r6_pack_e_acquisition_authorization_preparation.json": {"status": "NOT_CREATED", "authorization_activated": False, "pack_e_acquisition_calls": 0, "pack_e_constructed": False},
                "r6_pack_e_acquisition_authorization_fingerprint.json": {"status": "NOT_CREATED"},
            })
        else:
            reports["fred_binding_resolution_report.json"]["existing_reference_found"] = True
            environment = {
                "object": "PRESIGNAL_V21_DESIGNED_DRIFT_2_R6_PACK_E_SOURCE_ENVIRONMENT_V1",
                "environment_identity": "R6_PACK_E_FRED_TREASURY_MINIMUM_V1",
                "episode_identity": EPISODE,
                "pack_a_identity": PACK_A,
                "pack_authorization_fingerprint": PACK_AUTH,
                "approved_source_identities": [SOURCE],
                "prospective_adapter_identities": [ADAPTER],
                "configuration_reference_identities": [CONFIG],
                "credential_reference_types": [CREDENTIAL_TYPE],
                "required_field_bindings": {"TREASURY_2Y_10Y_PRESESSION_STATE": {"source_id": SOURCE, "series": ["DGS2", "DGS10"], "canonical_fields": ["US2Y_YIELD_LEVEL", "US10Y_YIELD_LEVEL", "US2Y_CHANGE_FROM_PRIOR_CLOSE", "US10Y_CHANGE_FROM_PRIOR_CLOSE", "US10Y_MINUS_US2Y_CURVE"]}},
                "optional_field_bindings": {"DXY_PRESESSION_STATE": "KSRC_FMP available but not selected for the current minimum environment", "USDJPY_PRESESSION_STATE": "KSRC_EODHD optional and not selected"},
                "per_source_acquisition_budgets": {SOURCE: 2},
                "total_acquisition_budget": 2,
                "retry_budget": 0,
                "forecast_cutoff": CUTOFF,
                "failure_stop_policy": "stop_on_source_failure_no_fallback",
                "probe_evidence_checksum": sha(redact(raw_result)),
            }
            environment["environment_fingerprint"] = sha(environment)
            acquisition = {
                "authorization_name": "PRESIGNAL_V21_DESIGNED_DRIFT_2_NEW_R6_PACK_E_ACQUISITION_AUTHORIZATION_V1",
                "status": "PREPARED_NOT_ACTIVATED",
                "source_environment_fingerprint": environment["environment_fingerprint"],
                "pack_authorization_fingerprint": PACK_AUTH,
                "route_b_freeze_fingerprint": ROUTE_B,
                "episode_identity": EPISODE,
                "pack_a_identity": PACK_A,
                "approved_source_identities": [SOURCE],
                "prospective_adapter_identities": [ADAPTER],
                "required_pack_e_field_coverage": environment["required_field_bindings"],
                "configuration_reference_classifications": {SOURCE: "EXISTING_SCRIPT_PROPERTY_PROVEN_BY_ONE_BOUNDED_PROBE"},
                "per_source_call_budgets": {SOURCE: 2},
                "total_call_budget": 2,
                "retry_budget": 0,
                "forecast_cutoff": CUTOFF,
                "secret_safety_contract": "reference_only_no_secret_values_or_headers",
                "failure_stop_policy": "stop_on_source_failure_no_fallback",
                "authorization_activated": False,
                "pack_e_acquisition_calls": 0,
                "pack_e_constructed": False,
            }
            acquisition["authorization_fingerprint"] = sha(acquisition)
            reports.update({
                "pack_e_minimum_environment_revalidation.json": {"runtime_ready": True, "source_identities": [SOURCE], "eodhd_excluded_as_optional": True, "fmp_not_selected_for_minimum": True, "missing_required_fields": [], "probe_record_persisted_as_pack_e_evidence": False},
                "r6_pack_e_source_environment.json": environment,
                "r6_pack_e_source_environment_fingerprint.json": {"environment_fingerprint": environment["environment_fingerprint"], "deterministic": True},
                "r6_pack_e_acquisition_authorization_preparation.json": acquisition,
                "r6_pack_e_acquisition_authorization_fingerprint.json": {"authorization_fingerprint": acquisition["authorization_fingerprint"], "deterministic": True},
            })
            decision = "NEW_R6_PACK_E_FRED_BINDING_PROVEN_ACQUISITION_AUTHORIZATION_PREPARED"
    reports["external_access_audit.json"] = external
    reports["final_fred_binding_resolution_decision.json"] = {"decision": decision, "cutoff_open": cutoff_open(timestamp), "probe_attempted": external["apps_script_executions"] == 1, "pack_e_acquisition_calls": 0, "pack_e_constructed": False}
    for name, value in reports.items():
        write(output, name, value)
    return decision


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--output", type=Path, default=OUT); parser.add_argument("--no-dispatch", action="store_true"); parser.add_argument("--at-utc")
    args = parser.parse_args()
    print(canonical({"decision": run(args.output, dispatch=not args.no_dispatch, at_utc=args.at_utc), "output": str(args.output.relative_to(ROOT))}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
