"""One bounded Gemini native-Attention execution for the selected FOMC Episode."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from automation import google_clients
from automation import presignal_v21_native_attention_call_v1 as call
from automation import presignal_v21_native_input_materialization_v1 as native

OUT = ROOT / "outputs/presignal_v21_designed_drift_r6_native_attention_fomc" / "R6-NATIVE-ATTENTION-FOMC-20260724-v1"
SELECT = ROOT / "outputs/presignal_v21_designed_drift_r6_episode_selection_fomc" / "R6-EPISODE-SELECTION-FOMC-20260724-v1"
PACKAGE_FP = "sha256:886d306ea6a28f54368121645f66523ee4a01310c65417b6e15c28a2132a29f7"
SELECTION_FP = "sha256:5d673811c40d006ae4630d0fde122a04aa20ab907781d3a762568e7b837389b8"
ATTENTION_FP = "sha256:3d72a513fc161fcb82c3b3bb0e635ccdd970441933102ed32cbcf34ee63f990d"
EPISODE = "EP_EVENT_68a8e1cc3c9bf6ccc385"
CUTOFF = "2026-07-29T18:00:00Z"
TOKEN = Path("/Users/junhoshino/projects/presignal/local/token.json")
REQUEST_PROMPT, REQUEST_PROMPT_SHA = "presignal_v21_information_request_prompt_v2", "sha256:219b3d33989d06b5f1968f6024c0135454320cf6c8f545116c6595d630011cb5"
ENUM_SHA, TEMPORAL_SHA = "sha256:320dad35692df096ea54466c17a8f02cff6287899aa3b7755dea00d7362bfb52", "sha256:d557c0733cc59982c46f71efaa89dad03a27e0d0c6023ba54eb2ef807c84c570"


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical(value).encode()).hexdigest()


def load(name: str) -> Any:
    return json.loads((SELECT / name).read_text(encoding="utf-8"))


def write(name: str, value: Any) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(canonical(value) + "\n", encoding="utf-8")


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def forbidden_content(raw: Mapping[str, Any]) -> dict[str, bool]:
    text = " ".join(str(item.get(key, "")) for item in raw.get("attention_items", []) if isinstance(item, Mapping) for key in ("attention_reason", "expected_market_channel", "driver_role")) + " " + str(raw.get("session_attention_summary", ""))
    lower = text.lower()
    return {"forecast_content_detected": any(x in lower for x in ("usdjpy direction", "pip magnitude", "price path", "buy ", "sell ")),
            "information_request_content_detected": any(x in lower for x in ("information request", "please collect", "request the following"))}


def validate() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    prepared = load("new_r6_attention_authorization_preparation.json")
    selection = load("new_r6_episode_selection_authorization.json")
    manifest = load("new_r6_selected_episode_manifest.json")
    ok = (prepared.get("authorization_fingerprint") == ATTENTION_FP and sha({k: v for k, v in prepared.items() if k != "authorization_fingerprint"}) == ATTENTION_FP and
          sha(selection) == SELECTION_FP and selection.get("episode_identity") == EPISODE and manifest.get("episode_identity") == EPISODE and
          manifest.get("content_checksum") == "sha256:e74f17bbd1e9b8a5cf6920c256f44a99decbf66af77dd716da81028611765143" and
          prepared.get("provider") == "Gemini" and prepared.get("model") == "gemini-2.5-flash-lite" and prepared.get("attention_call_budget") == 1 and prepared.get("retry_count") == 0)
    return prepared, manifest, {"authorization_valid": ok, "prepared_authorization_name": prepared.get("authorization_name"), "prepared_authorization_fingerprint": prepared.get("authorization_fingerprint"), "episode_selection_authorization_fingerprint": sha(selection), "episode_identity": manifest.get("episode_identity"), "provider": prepared.get("provider"), "model": prepared.get("model"), "call_budget": prepared.get("attention_call_budget"), "retry_budget": prepared.get("retry_count")}


def dispatch(request: Mapping[str, Any]) -> dict[str, Any]:
    """The established provider bridge is the sole Gemini transport boundary."""
    credentials = google_clients.load_credentials(False, token_path=TOKEN, persist_refresh=False)
    service = google_clients.build_script_service(credentials, 240)
    result = google_clients.run_script_function_with_metadata(service, google_clients.default_script_id(), "apiCallAuthoritativeProviderJsonObject", [dict(request)])
    if not result.get("ok"):
        return {"status": "transport_failure", "transport": result}
    return dict(result["result"]) if isinstance(result.get("result"), Mapping) else {"status": "provider_contract_error", "error": "BRIDGE_RESULT_NOT_OBJECT", "transport": result}


def run(*, do_dispatch: bool, at_utc: str | None = None) -> str:
    audit = {"calendar_refreshes": 0, "apps_script_executions": 0, "fmp_calls": 0, "google_reads": 0, "google_writes": 0, "gemini_calls": 0, "attention_calls": 0, "information_request_calls": 0, "forecast_calls": 0, "pack_a_constructions": 0, "pack_e_acquisitions": 0, "pack_e_computations": 0, "r6_evidence_writes": 0, "outcome_operations": 0, "evaluation_operations": 0}
    prepared, selected, validation = validate()
    timestamp = at_utc or now()
    if not validation["authorization_valid"]:
        decision = "NEW_R6_NATIVE_ATTENTION_BLOCKED_AUTHORIZATION_MISMATCH"
        artifacts = {"new_r6_attention_authorization_validation.json": validation, "new_r6_attention_request_envelope.json": {"status": "NOT_EXECUTED"}, "new_r6_attention_request_checksum.json": {"status": "NOT_CREATED"}, "new_r6_attention_raw_response.json": {"status": "NOT_EXECUTED"}, "new_r6_attention_transport_report.json": {"status": "NOT_EXECUTED"}, "new_r6_attention_schema_validation.json": {"status": "NOT_EXECUTED"}, "new_r6_attention_provider_source_role_report.json": {"status": "NOT_EXECUTED"}, "new_r6_attention_normalized_response.json": {"status": "NOT_CREATED"}, "new_r6_native_attention.json": {"status": "NOT_CREATED"}, "new_r6_attention_determinism_report.json": {"status": "NOT_EXECUTED"}, "new_r6_information_request_authorization_preparation.json": {"status": "NOT_CREATED"}}
    elif call.parse_utc(timestamp) >= call.parse_utc(CUTOFF):
        decision = "NEW_R6_NATIVE_ATTENTION_BLOCKED_CUTOFF_CLOSED"
        artifacts = {"new_r6_attention_authorization_validation.json": validation, "new_r6_attention_request_envelope.json": {"status": "NOT_EXECUTED", "reason": decision}, "new_r6_attention_request_checksum.json": {"status": "NOT_CREATED"}, "new_r6_attention_raw_response.json": {"status": "NOT_EXECUTED"}, "new_r6_attention_transport_report.json": {"status": "NOT_EXECUTED"}, "new_r6_attention_schema_validation.json": {"status": "NOT_EXECUTED"}, "new_r6_attention_provider_source_role_report.json": {"status": "NOT_EXECUTED"}, "new_r6_attention_normalized_response.json": {"status": "NOT_CREATED"}, "new_r6_native_attention.json": {"status": "NOT_CREATED"}, "new_r6_attention_determinism_report.json": {"status": "NOT_EXECUTED"}, "new_r6_information_request_authorization_preparation.json": {"status": "NOT_CREATED"}}
    else:
        episode = {"episode_identity": selected["episode_identity"], "episode_id": selected["episode_identity"], "primary_event_identity": selected["primary_event_identity"], "primary_event_id": selected["primary_event_identity"], "event_name": selected["primary_event_name"], "release_ts": selected["release_timestamp"], "forecast_cutoff": selected["forecast_cutoff"], "forecast_cutoff_ts": selected["forecast_cutoff"], "schema_version": selected["schema_version"], "country": selected["country"], "market_session_context": "STANDALONE_EVENT", "member_event_ids": [selected["primary_event_identity"]], "secondary_event_identities": []}
        member = {"event_id": selected["primary_event_identity"], "batch_id": "", "type": "single", "indicator_name": selected["primary_event_name"], "genre": "Monetary Policy", "importance": "High", "release_ts": selected["release_timestamp"], "member_order": 1}
        pre = call.attention_call_input(episode=episode, effective_timestamp=timestamp, collection_run_id="R6_FOMC_NATIVE_ATTENTION_20260724", member_rows=[member])
        envelope = {"authorization_fingerprint": ATTENTION_FP, "episode_identity": EPISODE, "primary_event_identity": member["event_id"], "primary_event_name": member["indicator_name"], "release_timestamp": selected["release_timestamp"], "forecast_cutoff": CUTOFF, "provider": "Gemini", "model": "gemini-2.5-flash-lite", "attention_prompt_version": call.PROMPT_VERSION, "attention_response_schema_version": call.RESPONSE_SCHEMA_VERSION, "request_timestamp": timestamp, "bridge_request": pre["bridge_request"]}
        if not do_dispatch:
            raise ValueError("DISPATCH_FLAG_REQUIRED")
        # This is the one and only authorized Gemini dispatch.  The bridge is
        # provider transport, not a calendar or scientific Google operation.
        audit["apps_script_executions"] = 1; audit["gemini_calls"] = 1; audit["attention_calls"] = 1
        response = dispatch(pre["bridge_request"])
        transport = {key: response.get(key) for key in ("status", "requested_provider", "requested_model", "actual_provider", "actual_model", "request_id", "request_status", "response_status", "terminal_status", "started_timestamp", "completed_timestamp", "prompt_tokens", "completion_tokens", "stop_reason", "error")}
        raw = response.get("raw_output")
        artifacts = {"new_r6_attention_authorization_validation.json": {**validation, "authorization_activated": True}, "new_r6_attention_request_envelope.json": envelope, "new_r6_attention_request_checksum.json": {"request_content_checksum": sha({k: v for k, v in envelope.items() if k not in {"request_timestamp"}})}, "new_r6_attention_raw_response.json": {"raw_response": raw, "raw_response_checksum": sha(raw)}, "new_r6_attention_transport_report.json": transport}
        try:
            if response.get("status") != "ok":
                raise call.NativeAttentionCallError("ATTENTION_TRANSPORT_OR_PROVIDER_FAILURE")
            raw_object = dict(raw) if isinstance(raw, Mapping) else json.loads(str(raw))
            content_flags = forbidden_content(raw_object)
            if any(content_flags.values()):
                raise call.NativeAttentionCallError("ATTENTION_FORBIDDEN_CONTENT")
            # The exact frozen Gemini bridge role is separated from trusted
            # transport identity; it is never treated as an LLM alias.
            normalized = call.normalize_preserved_gemini_attention_response(episode=episode, raw_response=raw_object, effective_timestamp=str(response.get("completed_timestamp") or timestamp), member_event_ids=[member["event_id"]], prompt_template_checksum=pre["prompt_template_checksum"], bridge_source_checksum="sha256:" + hashlib.sha256((ROOT / "apps_script/authoritative_provider_bridge.js").read_bytes()).hexdigest(), preserved_raw_response_checksum=sha(raw))
            source_roles = {"transport_provider_identity": normalized["transport_provider_identity"], "transport_model_identity": normalized["transport_model_identity"], "canonical_provider_identity": normalized["canonical_provider_identity"], "payload_provider_role": normalized["payload_provider_role"], "payload_role_is_llm_alias": False, **content_flags}
            schema_valid = {"schema_valid": True, "episode_identity_valid": normalized["episode_identity"] == EPISODE, "provider_identity_valid": normalized["canonical_provider_identity"] == "Gemini", "model_identity_valid": normalized["model_identity"] == "gemini-2.5-flash-lite", "selection_state": normalized["selection_state"], "acceptance_state": normalized["acceptance_state"], **content_flags}
            if normalized["selection_state"] == "SELECTED_FOR_INFORMATION_REQUESTS" and normalized["acceptance_state"] == "ACCEPTED":
                attention = native.materialize_selected_native_attention(episode=episode, provider="Gemini", model="gemini-2.5-flash-lite", prompt_version=call.PROMPT_VERSION, selection_state=normalized["selection_state"], acceptance_state=normalized["acceptance_state"], selection_reason=normalized["selection_reason"], effective_timestamp=normalized["effective_timestamp"], provenance={"attention_authorization_fingerprint": ATTENTION_FP, "selection_authorization_fingerprint": SELECTION_FP, "raw_response_checksum": normalized["raw_response_checksum"], "normalized_response_checksum": normalized["normalized_response_checksum"], "payload_provider_role": normalized["payload_provider_role"], "bridge_metadata_checksum": normalized["bridge_metadata_checksum"]})
                attention["raw_response_checksum"] = normalized["raw_response_checksum"]; attention["normalized_response_checksum"] = normalized["normalized_response_checksum"]
                attention["content_checksum"] = sha({k: attention[k] for k in ("attention_identity", "episode_identity", "primary_event_identity", "provider_identity", "model_identity", "prompt_version", "selection_state", "acceptance_state", "selection_reason", "effective_timestamp", "forecast_cutoff", "schema_version")})
                req_auth = {"authorization_name": "PRESIGNAL_V21_DESIGNED_DRIFT_2_NEW_R6_INFORMATION_REQUEST_CALL_AUTHORIZATION_V1", "status": "PREPARED_NOT_ACTIVATED", "episode_count": 1, "episode_identity": EPISODE, "attention_authorization_fingerprint": ATTENTION_FP, "episode_selection_authorization_fingerprint": SELECTION_FP, "attention_identity": attention["attention_identity"], "attention_content_checksum": attention["content_checksum"], "attention_provenance_checksum": attention["provenance_checksum"], "attention_lineage_checksum": attention["lineage_checksum"], "provider": "Gemini", "model": "gemini-2.5-flash-lite", "request_prompt_version": REQUEST_PROMPT, "request_prompt_checksum": REQUEST_PROMPT_SHA, "category_enum_checksum": ENUM_SHA, "temporal_alignment_fingerprint": TEMPORAL_SHA, "information_request_call_budget": 1, "retry_count": 0, "forecast_calls": 0, "acquisition_calls": 0, "forecast_cutoff": CUTOFF, "authorization_activated": False, "request_call_executed": False}
                req_auth["authorization_fingerprint"] = sha({k: v for k, v in req_auth.items() if k != "authorization_fingerprint"})
                runs = [native.materialize_selected_native_attention(episode=episode, provider="Gemini", model="gemini-2.5-flash-lite", prompt_version=call.PROMPT_VERSION, selection_state=normalized["selection_state"], acceptance_state=normalized["acceptance_state"], selection_reason=normalized["selection_reason"], effective_timestamp=normalized["effective_timestamp"], provenance=attention["provenance"]) for _ in range(3)]
                decision = "NEW_R6_NATIVE_ATTENTION_ACCEPTED_REQUEST_AUTHORIZATION_PREPARED"
                artifacts.update({"new_r6_attention_normalized_response.json": normalized, "new_r6_attention_schema_validation.json": schema_valid, "new_r6_attention_provider_source_role_report.json": source_roles, "new_r6_native_attention.json": attention, "new_r6_attention_determinism_report.json": {"runs": 3, "identical": len({sha(x) for x in runs}) == 1, "attention_identity": attention["attention_identity"]}, "new_r6_information_request_authorization_preparation.json": req_auth})
            else:
                decision = "NEW_R6_NATIVE_ATTENTION_NOT_SELECTED"
                artifacts.update({"new_r6_attention_normalized_response.json": normalized, "new_r6_attention_schema_validation.json": schema_valid, "new_r6_attention_provider_source_role_report.json": source_roles, "new_r6_native_attention.json": {"status": "NOT_CREATED_VALID_NOT_SELECTED"}, "new_r6_attention_determinism_report.json": {"runs": 1, "identical": True}, "new_r6_information_request_authorization_preparation.json": {"status": "NOT_CREATED"}})
        except call.NativeAttentionCallError as exc:
            decision = "NEW_R6_NATIVE_ATTENTION_RESPONSE_INVALID" if response.get("status") == "ok" else "NEW_R6_NATIVE_ATTENTION_CALL_FAILED"
            artifacts.update({"new_r6_attention_normalized_response.json": {"status": "INVALID", "reason": str(exc)}, "new_r6_attention_schema_validation.json": {"schema_valid": False, "reason": str(exc)}, "new_r6_attention_provider_source_role_report.json": {"status": "NOT_VALIDATED"}, "new_r6_native_attention.json": {"status": "NOT_CREATED"}, "new_r6_attention_determinism_report.json": {"status": "NOT_EXECUTED"}, "new_r6_information_request_authorization_preparation.json": {"status": "NOT_CREATED"}})
    artifacts["external_access_audit.json"] = audit
    artifacts["final_new_r6_native_attention_decision.json"] = {"decision": decision, "provider_call_attempted": audit["gemini_calls"] == 1, "information_request_call_executed": False}
    for name, value in artifacts.items(): write(name, value)
    return decision


def analyze_preserved() -> str:
    """Report every independently observable divergence after the sole call.

    This is deliberately offline: it never dispatches, normalizes into a
    canonical Attention, or changes the raw response evidence.
    """
    raw_evidence = json.loads((OUT / "new_r6_attention_raw_response.json").read_text(encoding="utf-8"))
    raw_value = raw_evidence.get("raw_response")
    try:
        raw = dict(raw_value) if isinstance(raw_value, Mapping) else json.loads(str(raw_value))
    except Exception:
        raw = {}
    member_ids = [str(item.get("event_id") or "") for item in raw.get("attention_items", []) if isinstance(item, Mapping)]
    divergences = []
    if raw.get("provider") != call.TRUSTED_GEMINI_PAYLOAD_ROLE:
        divergences.append("ATTENTION_BRIDGE_PAYLOAD_ROLE_MISMATCH")
    if member_ids != ["5ea0-ce20-ad20-fba0"] or len(set(member_ids)) != len(member_ids):
        divergences.append("ATTENTION_MEMBER_LINEAGE_MISMATCH")
    flags = forbidden_content(raw)
    write("new_r6_attention_schema_validation.json", {"schema_valid": False, "all_detected_divergences": divergences,
                                                         "first_deterministic_divergence": divergences[0] if divergences else None,
                                                         "forecast_content_detected": flags["forecast_content_detected"],
                                                         "information_request_content_detected": flags["information_request_content_detected"]})
    write("new_r6_attention_provider_source_role_report.json", {"transport_provider_identity": "Gemini", "transport_model_identity": "gemini-2.5-flash-lite",
                                                                   "raw_payload_provider_value": raw.get("provider"), "payload_role_classification": "UNTRUSTED_PAYLOAD_ROLE_VALUE",
                                                                   "canonical_provider_created": False, "payload_provider_treated_as_gemini_alias": False})
    write("new_r6_attention_normalized_response.json", {"status": "INVALID", "reason": divergences[0] if divergences else "ATTENTION_RAW_RESPONSE_INVALID", "raw_response_unchanged": True})
    write("new_r6_native_attention.json", {"status": "NOT_CREATED"})
    write("new_r6_information_request_authorization_preparation.json", {"status": "NOT_CREATED", "reason": "ATTENTION_NOT_ACCEPTED"})
    write("new_r6_attention_determinism_report.json", {"status": "NOT_EXECUTED_INVALID_RESPONSE", "provider_calls": 0, "raw_response_checksum": raw_evidence.get("raw_response_checksum")})
    return "NEW_R6_NATIVE_ATTENTION_RESPONSE_INVALID"


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(); parser.add_argument("--dispatch", action="store_true"); parser.add_argument("--at-utc"); parser.add_argument("--analyze-preserved", action="store_true")
    args = parser.parse_args(); decision = analyze_preserved() if args.analyze_preserved else run(do_dispatch=args.dispatch, at_utc=args.at_utc)
    print(canonical({"decision": decision, "output": str(OUT.relative_to(ROOT))}))
