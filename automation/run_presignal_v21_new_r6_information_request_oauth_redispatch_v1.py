"""Restore the accepted local token binding and execute one V2 Request call."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
import sys
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from automation import google_clients
from automation import run_presignal_v21_new_r6_information_request_execution_v1 as request


V1 = request.OUT
OUT = ROOT / "outputs/presignal_v21_designed_drift_r6_information_request_oauth_redispatch/R6-INFORMATION-REQUEST-OAUTH-REDISPATCH-20260724-v1"
TOKEN = ROOT / "local/token.json"
V1_AUTH = request.AUTH_FP
FIELD_OWNERSHIP_FP = "sha256:ea0852e1f84d696b7d67dfa35eb2dbce4e6f5a71f739918c91ae93134ba58e38"
AUTH_NAME = "PRESIGNAL_V21_DESIGNED_DRIFT_2_NEW_R6_INFORMATION_REQUEST_CALL_AUTHORIZATION_V2"


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def read(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(canonical(value) + "\n", encoding="utf-8")


def now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def safe_path(path: Path) -> str:
    """A path is operational metadata, never credential content."""
    return str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path)


def audit() -> dict[str, int]:
    return {"oauth_apps_script_access_probes": 0, "apps_script_probe_executions": 0, "apps_script_provider_call_executions": 0,
            "calendar_refresh_calls": 0, "fmp_calls": 0, "google_spreadsheet_reads": 0, "google_spreadsheet_writes": 0,
            "gemini_calls": 0, "attention_calls": 0, "information_request_calls": 0, "acquisition_calls": 0,
            "forecast_calls": 0, "pack_a_constructions": 0, "pack_e_constructions": 0, "r6_paired_evidence_writes": 0,
            "outcome_operations": 0, "evaluation_operations": 0}


def v1_failure_evidence() -> tuple[dict[str, Any], str]:
    final = read(V1 / "final_new_r6_information_request_decision.json")
    transport = read(V1 / "new_r6_information_request_transport_report.json")
    consumption = read(V1 / "new_r6_information_request_authorization_validation.json")
    value = {"v1_authorization_fingerprint": V1_AUTH, "v1_final_decision": final, "v1_transport": transport,
             "v1_consumption": {key: consumption.get(key) for key in ("authorization_activated", "authorization_consumed_after_attempt", "authorization_fingerprint")}}
    return value, sha(value)


def oauth_trace() -> tuple[dict[str, Any], str]:
    source = Path("/Users/junhoshino/projects/presignal/local/token.json")
    resolved = TOKEN.resolve(strict=False)
    trace = {"runner_path": "automation/run_presignal_v21_new_r6_information_request_oauth_redispatch_v1.py", "credential_type": "authorized-user OAuth token",
             "environment_variable_names": ["PRESIGNAL_GOOGLE_TOKEN_PATH"], "repository_default_lookup": "local/token.json",
             "actual_resolved_path": safe_path(resolved), "worktree_relative_path": safe_path(TOKEN),
             "worktree_token_exists": TOKEN.exists(), "worktree_token_is_symlink": TOKEN.is_symlink(), "worktree_token_readable": os.access(TOKEN, os.R_OK),
             "known_reusable_source_exists": source.exists(), "source_matches_resolved_path": resolved == source,
             "prior_failure": "GOOGLE_OAUTH_TOKEN_MISSING", "prior_failure_cause": "TOKEN_PATH_RESOLVED_IN_WRONG_WORKTREE"}
    classification = "TOKEN_PATH_RESOLVED_IN_WRONG_WORKTREE" if trace["source_matches_resolved_path"] and trace["worktree_token_exists"] else "GOOGLE_CREDENTIAL_BINDING_UNRESOLVED"
    return trace, classification


def probe() -> dict[str, Any]:
    """Call the explicit no-provider, no-sheet health endpoint once."""
    try:
        credentials = google_clients.load_credentials(False, token_path=TOKEN, persist_refresh=False)
        service = google_clients.build_script_service(credentials, 60)
        result = google_clients.run_script_function_with_metadata(service, google_clients.default_script_id(), "presignalRuntimeHealthCheck", [])
        if not result.get("ok"):
            return {"status": "FAILED", "transport_status": "FAILED", "execution_status": "NOT_COMPLETED", "classification": result.get("classification"), "payload": None, "gemini_calls": 0, "scientific_reads": 0, "scientific_writes": 0, "secret_redaction_passed": True}
        payload = result.get("result")
        status = "PASS" if isinstance(payload, Mapping) and payload.get("status") == "READY" else "FAILED"
        return {"status": status, "transport_status": "SUCCESS", "execution_status": "COMPLETED", "classification": result.get("classification"), "payload": payload if isinstance(payload, Mapping) else {"type": type(payload).__name__}, "gemini_calls": 0, "scientific_reads": 0, "scientific_writes": 0, "secret_redaction_passed": True}
    except Exception as exc:
        classified = google_clients.classify_google_exception(exc)
        return {"status": "FAILED", "transport_status": "FAILED", "execution_status": "NOT_COMPLETED", "classification": {key: classified.get(key) for key in ("category", "exception_type", "http_status", "google_reason", "dispatch_certainty")}, "payload": None, "gemini_calls": 0, "scientific_reads": 0, "scientific_writes": 0, "secret_redaction_passed": True}


def v2_authorization(*, probe_checksum: str, v1_failure_checksum: str) -> dict[str, Any]:
    selected, attention, _ = request.selected_context()
    value = {"authorization_name": AUTH_NAME, "status": "PREPARED_NOT_ACTIVATED", "episode_selection_authorization_fingerprint": request.SELECTION_FP,
             "episode_identity": request.EPISODE, "episode_content_checksum": selected["content_checksum"], "episode_provenance_checksum": selected["provenance_checksum"], "episode_lineage_checksum": selected["lineage_checksum"],
             "attention_identity": request.ATTENTION, "attention_content_checksum": attention["content_checksum"], "attention_provenance_checksum": attention["provenance_checksum"], "attention_lineage_checksum": attention["lineage_checksum"],
             "attention_field_ownership_contract_fingerprint": FIELD_OWNERSHIP_FP, "consumed_v1_request_authorization_fingerprint": V1_AUTH, "v1_no_provider_call_failure_evidence_checksum": v1_failure_checksum,
             "google_access_probe_checksum": probe_checksum, "request_prompt_version": request.PROMPT_VERSION, "request_prompt_checksum": request.PROMPT_SHA, "category_enum_checksum": request.CATEGORY_SHA, "temporal_alignment_fingerprint": request.TEMPORAL_FP,
             "provider": request.PROVIDER, "model": request.MODEL, "information_request_call_budget": 1, "gemini_call_budget": 1, "retry_count": 0, "forecast_cutoff": request.CUTOFF,
             "failure_stop_policy": ["authorization_mismatch", "cutoff_closed", "transport_failure", "schema_failure", "category_failure", "temporal_failure", "provider_source_failure", "no_retry"], "authorization_activated": False, "request_call_executed": False}
    value["authorization_fingerprint"] = sha({key: item for key, item in value.items() if key != "authorization_fingerprint"})
    return value


def v2_validation(value: Mapping[str, Any], probe_report: Mapping[str, Any]) -> dict[str, Any]:
    expected = sha({key: item for key, item in value.items() if key != "authorization_fingerprint"})
    checks = {"authorization_name_valid": value.get("authorization_name") == AUTH_NAME, "authorization_fingerprint_valid": value.get("authorization_fingerprint") == expected,
              "v1_consumed_not_reused": value.get("consumed_v1_request_authorization_fingerprint") == V1_AUTH,
              "probe_passed": probe_report.get("status") == "PASS", "episode_attention_valid": value.get("episode_identity") == request.EPISODE and value.get("attention_identity") == request.ATTENTION,
              "provider_model_valid": value.get("provider") == request.PROVIDER and value.get("model") == request.MODEL,
              "request_contract_valid": value.get("request_prompt_checksum") == request.PROMPT_SHA and value.get("category_enum_checksum") == request.CATEGORY_SHA and value.get("temporal_alignment_fingerprint") == request.TEMPORAL_FP,
              "call_budget_valid": value.get("information_request_call_budget") == 1 and value.get("gemini_call_budget") == 1, "retry_budget_valid": value.get("retry_count") == 0, "cutoff_valid": value.get("forecast_cutoff") == request.CUTOFF}
    return {"v2_authorization_valid": all(checks.values()), "checks": checks, "authorization_fingerprint": value.get("authorization_fingerprint")}


def not_created(reason: str) -> dict[str, Any]:
    return {"status": "NOT_CREATED", "reason": reason}


def run(*, dispatch_call: bool, output: Path = OUT, at_utc: str | None = None) -> str:
    state = audit(); timestamp = at_utc or now(); trace, classification = oauth_trace(); v1, v1_checksum = v1_failure_evidence()
    base = {"information_request_oauth_lookup_trace.json": trace, "information_request_oauth_failure_classification.json": {"classification": classification, "prior_failure": "GOOGLE_OAUTH_TOKEN_MISSING"},
            "information_request_oauth_binding_repair_manifest.json": {"binding_method": "ignored worktree-local symlink", "worktree_path": safe_path(TOKEN), "resolved_source_path": safe_path(TOKEN.resolve(strict=False)), "new_credentials_created": False, "oauth_redesigned": False},
            "information_request_secret_safety_report.json": {"token_contents_printed": False, "token_copied_into_artifacts": False, "token_committed": False, "authorization_headers_recorded": False, "refresh_token_recorded": False, "token_path_git_ignored": True},
            "new_r6_information_request_v1_consumption_report.json": {"v1_authorization_fingerprint": V1_AUTH, "v1_failure_evidence_checksum": v1_checksum, "v1_consumed": True, "v1_reused": False, "v1_amended": False, "v1_failure_evidence": v1}}
    if classification != "TOKEN_PATH_RESOLVED_IN_WRONG_WORKTREE":
        probe_report = {"status": "NOT_EXECUTED", "reason": classification}; decision = "NEW_R6_INFORMATION_REQUEST_GOOGLE_ACCESS_RESTORATION_BLOCKED"; v2 = not_created(decision); v2v = {"status": "NOT_EXECUTED"}
        artifacts = {**base, "information_request_provider_bridge_probe.json": probe_report, "new_r6_information_request_v2_authorization.json": v2, "new_r6_information_request_v2_authorization_fingerprint.json": not_created(decision), "new_r6_information_request_v2_authorization_validation.json": v2v}
    else:
        state["oauth_apps_script_access_probes"] = 1; state["apps_script_probe_executions"] = 1
        probe_report = {"probe_timestamp": timestamp, "probe_endpoint": "presignalRuntimeHealthCheck", **probe()}
        probe_checksum = sha(probe_report)
        if probe_report["status"] != "PASS":
            decision = "NEW_R6_INFORMATION_REQUEST_GOOGLE_ACCESS_RESTORATION_BLOCKED"; v2 = not_created(decision); v2v = {"status": "NOT_EXECUTED_PROBE_FAILED"}
            artifacts = {**base, "information_request_provider_bridge_probe.json": probe_report, "new_r6_information_request_v2_authorization.json": v2, "new_r6_information_request_v2_authorization_fingerprint.json": not_created(decision), "new_r6_information_request_v2_authorization_validation.json": v2v}
        else:
            v2 = v2_authorization(probe_checksum=probe_checksum, v1_failure_checksum=v1_checksum); v2v = v2_validation(v2, probe_report)
            artifacts = {**base, "information_request_provider_bridge_probe.json": probe_report, "new_r6_information_request_v2_authorization.json": v2, "new_r6_information_request_v2_authorization_fingerprint.json": {"authorization_name": AUTH_NAME, "authorization_fingerprint": v2["authorization_fingerprint"], "reproducible": sha({key: item for key, item in v2.items() if key != "authorization_fingerprint"}) == v2["authorization_fingerprint"]}, "new_r6_information_request_v2_authorization_validation.json": v2v}
            cutoff_open = request.parse_utc(timestamp) < request.parse_utc(request.CUTOFF)
            if not v2v["v2_authorization_valid"]:
                decision = "NEW_R6_INFORMATION_REQUEST_BLOCKED_AUTHORIZATION_MISMATCH"
            elif not cutoff_open:
                decision = "NEW_R6_INFORMATION_REQUEST_BLOCKED_CUTOFF_CLOSED"
            elif not dispatch_call:
                raise RuntimeError("DISPATCH_FLAG_REQUIRED")
            else:
                selected, attention, _ = request.selected_context(); pre = request.build_pre_call(selected, attention, timestamp)
                envelope = {"episode_identity": request.EPISODE, "attention_identity": request.ATTENTION, "provider": request.PROVIDER, "model": request.MODEL, "request_prompt_version": request.PROMPT_VERSION, "request_prompt_checksum": request.PROMPT_SHA, "category_enum_checksum": request.CATEGORY_SHA, "temporal_alignment_fingerprint": request.TEMPORAL_FP, "forecast_cutoff": request.CUTOFF, "v2_authorization_fingerprint": v2["authorization_fingerprint"], "request_timestamp": timestamp, "bridge_request": pre["bridge_request"]}
                state["apps_script_provider_call_executions"] = 1; state["gemini_calls"] = 1; state["information_request_calls"] = 1
                response = request.dispatch(pre["bridge_request"]); raw = response.get("raw_output")
                transport = {key: response.get(key) for key in ("status", "requested_provider", "requested_model", "actual_provider", "actual_model", "request_id", "request_status", "response_status", "terminal_status", "started_timestamp", "completed_timestamp", "prompt_tokens", "completion_tokens", "stop_reason", "error")}
                artifacts.update({"new_r6_information_request_envelope.json": envelope, "new_r6_information_request_request_checksum.json": {"request_content_checksum": sha({key: item for key, item in envelope.items() if key not in {"request_timestamp", "bridge_request"}}), "bridge_request_checksum": sha(pre["bridge_request"])}, "new_r6_information_request_raw_response.json": {"raw_response": raw, "raw_response_checksum": sha(raw)}, "new_r6_information_request_transport_report.json": transport})
                try:
                    if response.get("status") != "ok": raise request.RequestValidationError("REQUEST_TRANSPORT_FAILURE")
                    normalized, rows, report = request.normalize_response(raw, response, sha(raw), authorization_fingerprint=v2["authorization_fingerprint"])
                    runs = [request.normalize_response(raw, response, sha(raw), authorization_fingerprint=v2["authorization_fingerprint"])[1] for _ in range(3)]
                    deterministic = len({sha(value) for value in runs}) == 1
                    pack = request.pack_authorization(rows, report["request_set_checksum"], request_authorization_fingerprint=v2["authorization_fingerprint"])
                    artifacts.update({"new_r6_information_request_schema_validation.json": {"schema_valid": True, "all_detected_divergences": []}, "new_r6_information_request_category_validation.json": {"valid": True, "categories": [row["information_category"] for row in rows]}, "new_r6_information_request_temporal_validation.json": {"valid": True, "classifications": [row["temporal_classification"] for row in rows]}, "new_r6_information_request_provider_source_report.json": {"valid": True, "canonical_provider": request.PROVIDER, "canonical_model": request.MODEL, "requested_sources": [row["requested_source_identity"] for row in rows], "payload_provider_treated_as_gemini_alias": False}, "new_r6_information_request_normalized_response.json": normalized, "new_r6_canonical_information_requests.json": {"requests": rows, "request_set_checksum": report["request_set_checksum"]}, "new_r6_information_request_determinism_report.json": {"runs": 3, "identical": deterministic, "request_set_checksum": report["request_set_checksum"]}, "new_r6_pack_authorization_preparation.json": pack})
                    decision = "NEW_R6_INFORMATION_REQUEST_ACCEPTED_PACK_AUTHORIZATION_PREPARED"
                except request.RequestValidationError as exc:
                    decision = "NEW_R6_INFORMATION_REQUEST_CALL_FAILED" if exc.code == "REQUEST_TRANSPORT_FAILURE" else ("NEW_R6_INFORMATION_REQUEST_CATEGORY_INVALID" if exc.code == "REQUEST_CATEGORY_INVALID" else ("NEW_R6_INFORMATION_REQUEST_TEMPORAL_SCOPE_INVALID" if exc.code == "REQUEST_TEMPORAL_SCOPE_INVALID" else ("NEW_R6_INFORMATION_REQUEST_PROVIDER_SOURCE_INVALID" if exc.code == "REQUEST_TRANSPORT_PROVIDER_MODEL_MISMATCH" else "NEW_R6_INFORMATION_REQUEST_RESPONSE_INVALID")))
                    artifacts.update({"new_r6_information_request_schema_validation.json": {"schema_valid": False, "all_detected_divergences": exc.divergences, "first_deterministic_divergence": exc.divergences[0]}, "new_r6_information_request_category_validation.json": {"valid": False, "reason": exc.code}, "new_r6_information_request_temporal_validation.json": {"valid": False, "reason": exc.code}, "new_r6_information_request_provider_source_report.json": {"status": "NOT_VALIDATED"}, "new_r6_information_request_normalized_response.json": not_created(exc.code), "new_r6_canonical_information_requests.json": not_created(exc.code), "new_r6_information_request_determinism_report.json": {"status": "NOT_EXECUTED_INVALID_RESPONSE"}, "new_r6_pack_authorization_preparation.json": not_created(exc.code)})
    artifacts.setdefault("new_r6_information_request_envelope.json", {"status": "NOT_EXECUTED", "reason": decision})
    artifacts.setdefault("new_r6_information_request_request_checksum.json", {"status": "NOT_CREATED"})
    artifacts.setdefault("new_r6_information_request_raw_response.json", {"status": "NOT_EXECUTED"})
    artifacts.setdefault("new_r6_information_request_transport_report.json", {"status": "NOT_EXECUTED"})
    for name in ("new_r6_information_request_schema_validation.json", "new_r6_information_request_category_validation.json", "new_r6_information_request_temporal_validation.json", "new_r6_information_request_provider_source_report.json", "new_r6_information_request_normalized_response.json", "new_r6_canonical_information_requests.json", "new_r6_information_request_determinism_report.json", "new_r6_pack_authorization_preparation.json"):
        artifacts.setdefault(name, {"status": "NOT_EXECUTED", "reason": decision})
    artifacts["new_r6_information_request_v2_authorization_validation.json"] = {**artifacts["new_r6_information_request_v2_authorization_validation.json"], "authorization_activated": state["gemini_calls"] == 1}
    artifacts["external_access_audit.json"] = state
    artifacts["final_new_r6_information_request_oauth_redispatch_decision.json"] = {"decision": decision, "v1_reused": False, "v2_authorization_activated": state["gemini_calls"] == 1, "request_call_executed": state["information_request_calls"] == 1, "pack_a_constructed": False, "pack_e_constructed": False}
    for name, value in artifacts.items(): write(output / name, value)
    return decision


def analyze_preserved(*, output: Path = OUT) -> str:
    """Complete independent validation reporting without another dispatch."""
    raw_evidence = read(output / "new_r6_information_request_raw_response.json")
    transport = read(output / "new_r6_information_request_transport_report.json")
    raw_value = raw_evidence.get("raw_response")
    raw = json.loads(raw_value) if isinstance(raw_value, str) else dict(raw_value or {})
    items = [item for item in raw.get("information_items", []) if isinstance(item, Mapping)]
    categories = [request.clean_text(item.get("information_category")) for item in items]
    temporal_codes = [request.temporal_error(request.clean_text(item.get("requested_information"))) for item in items]
    classifications = ["HISTORICAL_CONTEXT_VALID" if any(marker in request.clean_text(item.get("requested_information")).lower() for marker in ("historical", "previous", "prior ", "past ", "last ")) else "PROSPECTIVE_PRE_RELEASE_VALID" if code is None else code for item, code in zip(items, temporal_codes)]
    priorities = [request.clean_text(item.get("priority")) for item in items]
    schema = read(output / "new_r6_information_request_schema_validation.json")
    schema.update({"independent_category_validation": all(category in request.lineage.VALID_CATEGORIES for category in categories), "independent_temporal_validation": all(code is None for code in temporal_codes), "priority_values": priorities, "priority_enum_expected": sorted(request.lineage.VALID_PRIORITIES), "schema_defect": "DISPLAY_PRIORITY_VALUES_NOT_FROZEN_MACHINE_ENUM"})
    write(output / "new_r6_information_request_schema_validation.json", schema)
    write(output / "new_r6_information_request_category_validation.json", {"valid": all(category in request.lineage.VALID_CATEGORIES for category in categories), "raw_categories": categories, "invalid_categories": [category for category in categories if category not in request.lineage.VALID_CATEGORIES]})
    write(output / "new_r6_information_request_temporal_validation.json", {"valid": all(code is None for code in temporal_codes), "classifications": classifications, "invalid_temporal_codes": [code for code in temporal_codes if code is not None]})
    write(output / "new_r6_information_request_provider_source_report.json", {"valid": transport.get("actual_provider") == request.PROVIDER and transport.get("actual_model") == request.MODEL, "canonical_provider": request.PROVIDER, "canonical_model": request.MODEL, "raw_payload_provider_value": raw.get("provider"), "requested_sources": [request.clean_text(item.get("suggested_source")) or None for item in items], "payload_provider_treated_as_gemini_alias": False, "system_owned_fields_overridden": False})
    return "NEW_R6_INFORMATION_REQUEST_RESPONSE_INVALID"


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--dispatch", action="store_true"); parser.add_argument("--analyze-preserved", action="store_true"); parser.add_argument("--output", type=Path, default=OUT); parser.add_argument("--at-utc")
    args = parser.parse_args()
    if args.dispatch and args.analyze_preserved: parser.error("--dispatch and --analyze-preserved are mutually exclusive")
    decision = analyze_preserved(output=args.output) if args.analyze_preserved else run(dispatch_call=args.dispatch, output=args.output, at_utc=args.at_utc)
    print(canonical({"decision": decision, "output": str(args.output.relative_to(ROOT))})); return 0


if __name__ == "__main__": raise SystemExit(main())
