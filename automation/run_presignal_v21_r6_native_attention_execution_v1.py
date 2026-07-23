"""Execute exactly one authorized Gemini Attention call for the selected R6 Episode.

This runner deliberately owns only the bounded provider call and local evidence
package.  It does not read Sheets, write Google state, build Requests/Packs, or
perform any forecast, acquisition, Outcome, or evaluation operation.
"""
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
from automation import presignal_v21_native_attention_call_v1 as call
from automation import presignal_v21_native_input_materialization_v1 as native

SELECTION_DIR = ROOT / "outputs" / "presignal_v21_designed_drift_r6_episode_selection" / "R6-EPISODE-SELECTION-AUTHORIZATION-20260723-v1"
REFRESH_DIR = ROOT / "outputs" / "presignal_v21_designed_drift_r6_episode_refresh" / "R6-EPISODE-REFRESH-20260723-v1"
OUTPUT = ROOT / "outputs" / "presignal_v21_designed_drift_r6_native_attention_execution" / "R6-NATIVE-ATTENTION-EXECUTION-20260723-v1"
SELECTED_EPISODE_ID = "EP_BATCH_0b3bf1cac3c02da74063"
EXPECTED_EPISODE_CHECKSUM = "sha256:64cca8b9d148fe795ef154273be8b12f0f405ee09e1308c5dfc1d246933a77f1"
SELECTION_FINGERPRINT = "sha256:73e8fe3f89126d9129ef6bcbbaeedeaf79d9f148d367248f9dcc778b307827e1"


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(canonical(value) + "\n", encoding="utf-8")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def file_checksum(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def load_frozen_episode() -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    selection = read_json(SELECTION_DIR / "episode_selection_authorization_manifest.json")
    selection_fp = read_json(SELECTION_DIR / "episode_selection_authorization_fingerprint.json")
    inventory = read_json(SELECTION_DIR / "episode_selection_candidate_inventory.json")
    raw = read_json(REFRESH_DIR / "raw_event_inventory.json")
    candidate = next((dict(row) for row in inventory["candidates"] if row.get("episode_id") == SELECTED_EPISODE_ID), None)
    if candidate is None or call.checksum(candidate) != EXPECTED_EPISODE_CHECKSUM:
        raise ValueError("R6_NATIVE_ATTENTION_EXECUTION_BLOCKED_AUTHORIZATION_MISMATCH:episode_checksum")
    if selection.get("selected_episode_identity") != SELECTED_EPISODE_ID or selection.get("episode_content_checksum") != EXPECTED_EPISODE_CHECKSUM:
        raise ValueError("R6_NATIVE_ATTENTION_EXECUTION_BLOCKED_AUTHORIZATION_MISMATCH:selected_episode")
    if selection_fp.get("authorization_fingerprint") != SELECTION_FINGERPRINT or call.checksum(selection) != SELECTION_FINGERPRINT:
        raise ValueError("R6_NATIVE_ATTENTION_EXECUTION_BLOCKED_AUTHORIZATION_MISMATCH:selection_fingerprint")
    if (selection.get("route_b_freeze_fingerprint") != call.FREEZE_FINGERPRINT
            or selection.get("r6_authorization_v3_fingerprint") != call.R6_V3_FINGERPRINT
            or selection.get("native_attention_authorization_fingerprint") != call.checksum(call.authorization_manifest())):
        raise ValueError("R6_NATIVE_ATTENTION_EXECUTION_BLOCKED_AUTHORIZATION_MISMATCH:bound_fingerprint")
    event_by_id = {str(row.get("event_id")): dict(row) for row in raw.get("rows", [])}
    members = []
    for order, event_id in enumerate(candidate["member_event_ids"], 1):
        source = event_by_id.get(str(event_id))
        if source is None:
            raise ValueError("R6_NATIVE_ATTENTION_EXECUTION_BLOCKED_AUTHORIZATION_MISMATCH:member_source")
        members.append({"event_id": str(source["event_id"]), "batch_id": str(source.get("batch_id") or ""), "type": str(source.get("type") or "member"), "indicator_name": str(source["indicator_name"]), "genre": str(source.get("genre") or ""), "importance": str(source.get("importance") or ""), "release_ts": str(source["release_ts"]), "consensus_value": str(source.get("consensus_value") or ""), "prev_revision": str(source.get("prev_revision") or ""), "member_order": order})
    episode = {"episode_identity": candidate["episode_id"], "episode_id": candidate["episode_id"], "primary_event_identity": candidate["primary_event_id"], "primary_event_id": candidate["primary_event_id"], "event_name": candidate["primary_indicator_name"], "release_ts": candidate["release_ts"], "forecast_cutoff": candidate["forecast_cutoff_ts"], "forecast_cutoff_ts": candidate["forecast_cutoff_ts"], "schema_version": candidate["schema_version"], "country": candidate["country"], "market_session_context": candidate["market_session_context"], "member_event_ids": list(candidate["member_event_ids"]), "secondary_event_identities": list(candidate["secondary_event_identities"])}
    return episode, members, {"selection_manifest_checksum": file_checksum(SELECTION_DIR / "episode_selection_authorization_manifest.json"), "candidate_inventory_checksum": inventory["candidate_inventory_checksum"], "raw_event_inventory_checksum": raw["checksum"]}


def authorization_report(episode: Mapping[str, Any], provenance: Mapping[str, Any]) -> dict[str, Any]:
    return {"route_b_freeze_valid": call.FREEZE_FINGERPRINT == native.ROUTE_B_FREEZE, "r6_authorization_v3_valid": call.R6_V3_FINGERPRINT == "sha256:c8cb003af94eef2ef9cad8f323ab31b3c1990f3ffdcdab5ee3e6285fda76efb9", "native_attention_call_authorization_valid": call.checksum(call.authorization_manifest()) == "sha256:a5e1dfda5a637dbaf626c43c2bcdf512d36e2b24daff6f6ab3ce4adbd923db50", "episode_selection_authorization_valid": bool(provenance["selection_manifest_checksum"]), "episode_checksum_valid": True, "selected_episode_checksum": EXPECTED_EPISODE_CHECKSUM, "provider": call.PROVIDER, "model": call.MODEL, "call_budget": 1, "retry_count": 0, "forecast_calls_prohibited": True, "google_writes_prohibited": True, "outcome_prohibited": True, "evaluation_prohibited": True}


def _dispatch(payload: Mapping[str, Any], token_path: Path) -> dict[str, Any]:
    credentials = google_clients.load_credentials(False, token_path=token_path, persist_refresh=False)
    service = google_clients.build_script_service(credentials, 240)
    result = google_clients.run_script_function_with_metadata(service, google_clients.default_script_id(), "apiCallAuthoritativeProviderJsonObject", [dict(payload)])
    if not result.get("ok"):
        return {"status": "transport_failure", "transport": result}
    bridge = result.get("result")
    return dict(bridge) if isinstance(bridge, Mapping) else {"status": "provider_contract_error", "error": "BRIDGE_RESULT_NOT_OBJECT", "transport": result}


def run(*, output: Path, dispatch: bool, at_utc: str | None = None) -> int:
    audit = {"google_episode_validation_reads": 0, "apps_script_execution_calls": 0, "gemini_attention_calls": 0, "other_provider_calls": 0, "forecast_calls": 0, "http_acquisition_calls": 0, "market_data_calls": 0, "live_pack_e_computations": 0, "google_scientific_writes": 0, "r6_evidence_writes": 0, "historical_mutations": 0, "outcome_operations": 0, "evaluation_operations": 0}
    try:
        episode, members, provenance = load_frozen_episode()
        dispatch_time = at_utc or now_utc()
        if call.parse_utc(dispatch_time) >= call.parse_utc(episode["forecast_cutoff"]):
            decision = "R6_NATIVE_ATTENTION_EXECUTION_BLOCKED_CUTOFF_CLOSED"
            reports = {"authorization_validation_report.json": {"status": "PASS", **authorization_report(episode, provenance)}, "episode_cutoff_revalidation.json": {"current_utc": dispatch_time, "release_time": episode["release_ts"], "forecast_cutoff": episode["forecast_cutoff"], "cutoff_open": False, "episode_content_checksum": EXPECTED_EPISODE_CHECKSUM}, "attention_pre_call_manifest.json": {"status": "NOT_EXECUTED", "reason": decision}, "attention_provider_request.json": {"status": "NOT_EXECUTED"}, "attention_raw_response.json": {"status": "NOT_EXECUTED"}, "attention_normalized_response.json": {"status": "NOT_EXECUTED"}, "native_attention_object.json": {"status": "NOT_EXECUTED"}, "attention_validation_report.json": {"status": "NOT_EXECUTED"}, "attention_determinism_report.json": {"status": "NOT_EXECUTED"}, "provider_call_budget_report.json": {"calls_used": 0, "calls_remaining": 1, "retry_budget_remaining": 0}, "external_access_audit.json": audit, "final_native_attention_execution_decision.json": {"decision": decision, "call_attempted": False, "call_count": 0}}
        else:
            pre = call.attention_call_input(episode=episode, member_rows=members, effective_timestamp=dispatch_time, collection_run_id="R6_NATIVE_ATTENTION_EXECUTION_20260723")
            pre_manifest = {"authorization": {"route_b_freeze_fingerprint": call.FREEZE_FINGERPRINT, "r6_authorization_v3_fingerprint": call.R6_V3_FINGERPRINT, "native_attention_authorization_fingerprint": call.checksum(call.authorization_manifest()), "episode_selection_authorization_fingerprint": SELECTION_FINGERPRINT}, "episode_identity": episode["episode_identity"], "episode_checksum": EXPECTED_EPISODE_CHECKSUM, "primary_event_identity": episode["primary_event_identity"], "secondary_event_identities": episode["secondary_event_identities"], "release_time": episode["release_ts"], "forecast_cutoff": episode["forecast_cutoff"], "provider": call.PROVIDER, "model": call.MODEL, "attention_prompt_version": call.PROMPT_VERSION, "prompt_template_checksum": pre["prompt_template_checksum"], "resolved_prompt_checksum": pre["resolved_prompt_checksum"], "response_schema_version": call.RESPONSE_SCHEMA_VERSION, "response_schema_checksum": pre["response_schema_checksum"], "provider_call_parameters_checksum": pre["provider_call_parameters_checksum"], "call_sequence_number": 1, "retry_count": 0}
            if not dispatch:
                raise ValueError("DISPATCH_FLAG_REQUIRED")
            token_path = Path("/Users/junhoshino/projects/presignal/local/token.json")
            token_before = file_checksum(token_path)
            audit["apps_script_execution_calls"] = 1
            audit["gemini_attention_calls"] = 1
            response = _dispatch(pre["bridge_request"], token_path)
            token_after = file_checksum(token_path)
            raw = response.get("raw_output")
            base = {"authorization_validation_report.json": {"status": "PASS", **authorization_report(episode, provenance)}, "episode_cutoff_revalidation.json": {"current_utc": dispatch_time, "release_time": episode["release_ts"], "forecast_cutoff": episode["forecast_cutoff"], "cutoff_open": True, "episode_content_checksum": EXPECTED_EPISODE_CHECKSUM}, "attention_pre_call_manifest.json": pre_manifest, "attention_provider_request.json": pre["bridge_request"], "attention_raw_response.json": {"raw_response": raw, "raw_response_checksum": call.checksum(raw), "transport_metadata": {key: response.get(key) for key in ("status", "requested_provider", "requested_model", "actual_provider", "actual_model", "started_timestamp", "completed_timestamp", "request_status", "response_status", "terminal_status", "request_id", "prompt_tokens", "completion_tokens", "stop_reason", "error")}, "token_file_unchanged": token_before == token_after}}
            try:
                if response.get("status") != "ok":
                    raise call.NativeAttentionCallError("ATTENTION_TRANSPORT_OR_PROVIDER_FAILURE")
                raw_object = dict(raw) if isinstance(raw, Mapping) else json.loads(str(raw))
                normalized = call.normalize_attention_response(episode=episode, raw_response=raw_object, effective_timestamp=str(response.get("completed_timestamp") or dispatch_time), returned_provider=str(response.get("actual_provider") or ""), returned_model=str(response.get("actual_model") or ""), member_event_ids=[row["event_id"] for row in members])
                validation = {"status": "VALID", "episode_lineage_match": True, "provider_model_match": True, "schema_valid": True, "cutoff_valid": True}
                if normalized["selection_state"].startswith("SELECTED") and normalized["acceptance_state"] == "ACCEPTED":
                    attention = native.materialize_selected_native_attention(episode=episode, provider=call.PROVIDER, model=call.MODEL, prompt_version=call.PROMPT_VERSION, selection_state=normalized["selection_state"], acceptance_state=normalized["acceptance_state"], selection_reason=normalized["selection_reason"], effective_timestamp=normalized["effective_timestamp"], provenance={"authorization_fingerprint": SELECTION_FINGERPRINT, "raw_response_checksum": normalized["raw_response_checksum"], "normalized_response_checksum": normalized["normalized_response_checksum"], **provenance})
                    objects = [native.materialize_selected_native_attention(episode=episode, provider=call.PROVIDER, model=call.MODEL, prompt_version=call.PROMPT_VERSION, selection_state=normalized["selection_state"], acceptance_state=normalized["acceptance_state"], selection_reason=normalized["selection_reason"], effective_timestamp=normalized["effective_timestamp"], provenance=attention["provenance"]) for _ in range(3)]
                    stable = len({call.checksum(value) for value in objects}) == 1
                    decision = "NATIVE_ATTENTION_SELECTED_INPUT_MATERIALIZATION_READY"
                else:
                    attention = {"status": "NOT_MATERIALIZED_VALID_NOT_SELECTED", "normalized_response_checksum": normalized["normalized_response_checksum"]}
                    stable = True; decision = "NATIVE_ATTENTION_VALID_NOT_SELECTED_R6_STOPPED"
                base.update({"attention_normalized_response.json": normalized, "native_attention_object.json": attention, "attention_validation_report.json": validation, "attention_determinism_report.json": {"proof_runs": 3, "identical_runs": stable, "normalized_response_checksum": normalized["normalized_response_checksum"], "attention_identity": attention.get("attention_identity")}, "provider_call_budget_report.json": {"calls_used": 1, "calls_remaining": 0, "retry_budget_remaining": 0}, "external_access_audit.json": audit, "final_native_attention_execution_decision.json": {"decision": decision, "call_attempted": True, "call_count": 1, "episode_identity": episode["episode_identity"], "attention_identity": attention.get("attention_identity")}})
            except Exception as exc:
                base.update({"attention_normalized_response.json": {"status": "INVALID", "error": type(exc).__name__, "reason": str(exc)}, "native_attention_object.json": {"status": "NOT_MATERIALIZED"}, "attention_validation_report.json": {"status": "INVALID", "reason": str(exc)}, "attention_determinism_report.json": {"status": "NOT_EXECUTED_INVALID_RESPONSE", "proof_runs": 0}, "provider_call_budget_report.json": {"calls_used": 1, "calls_remaining": 0, "retry_budget_remaining": 0}, "external_access_audit.json": audit, "final_native_attention_execution_decision.json": {"decision": "NATIVE_ATTENTION_CALL_FAILED", "call_attempted": True, "call_count": 1, "failure": str(exc)}})
            reports = base
    except Exception as exc:
        reports = {"authorization_validation_report.json": {"status": "FAILED", "reason": str(exc)}, "episode_cutoff_revalidation.json": {"status": "NOT_EXECUTED"}, "attention_pre_call_manifest.json": {"status": "NOT_EXECUTED"}, "attention_provider_request.json": {"status": "NOT_EXECUTED"}, "attention_raw_response.json": {"status": "NOT_EXECUTED"}, "attention_normalized_response.json": {"status": "NOT_EXECUTED"}, "native_attention_object.json": {"status": "NOT_EXECUTED"}, "attention_validation_report.json": {"status": "NOT_EXECUTED"}, "attention_determinism_report.json": {"status": "NOT_EXECUTED"}, "provider_call_budget_report.json": {"calls_used": 0, "calls_remaining": 1, "retry_budget_remaining": 0}, "external_access_audit.json": audit, "final_native_attention_execution_decision.json": {"decision": "R6_NATIVE_ATTENTION_EXECUTION_BLOCKED_AUTHORIZATION_MISMATCH", "call_attempted": False, "call_count": 0, "failure": str(exc)}}
    for name, value in reports.items():
        write_json(output / name, value)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dispatch", action="store_true")
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--at-utc")
    args = parser.parse_args()
    return run(output=args.output, dispatch=args.dispatch, at_utc=args.at_utc)


if __name__ == "__main__":
    raise SystemExit(main())
