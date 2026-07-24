"""One bounded Gemini Information-Request execution for the selected FOMC Episode.

This runner deliberately keeps the provider transport separate from the
model-authored research payload.  It performs one call only when explicitly
invoked with ``--dispatch``; all other work is local evidence construction.
It neither reads nor writes a spreadsheet and never constructs either Pack.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
import sys
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from automation import google_clients
from automation import presignal_v21_minimal_prospective_lineage_v1 as lineage


SOURCE = ROOT / "outputs/presignal_v21_designed_drift_r6_native_attention_field_ownership/R6-NATIVE-ATTENTION-FIELD-OWNERSHIP-20260724-v1"
SELECT = ROOT / "outputs/presignal_v21_designed_drift_r6_episode_selection_fomc/R6-EPISODE-SELECTION-FOMC-20260724-v1"
OUT = ROOT / "outputs/presignal_v21_designed_drift_r6_information_request_fomc/R6-INFORMATION-REQUEST-FOMC-20260724-v1"
TOKEN = ROOT / "local/token.json"

EPISODE = "EP_EVENT_68a8e1cc3c9bf6ccc385"
ATTENTION = "NATTN_013be496bbbd13cf4bf6"
CUTOFF = "2026-07-29T18:00:00Z"
PROVIDER, MODEL = "Gemini", "gemini-2.5-flash-lite"
AUTH_FP = "sha256:a7b20488e55d4d75fbb8e578b89e34d6f131ce681dd204615b6b5db10e32be62"
SELECTION_FP = "sha256:5d673811c40d006ae4630d0fde122a04aa20ab907781d3a762568e7b837389b8"
ROUTE_B_FREEZE = "sha256:8c910a343515d88ca63ce4aaf738f28f9b4a8ab22665397077858bfaf7e866e4"
PROMPT_VERSION = "presignal_v21_information_request_prompt_v2"
PROMPT_SHA = "sha256:219b3d33989d06b5f1968f6024c0135454320cf6c8f545116c6595d630011cb5"
CATEGORY_SHA = "sha256:320dad35692df096ea54466c17a8f02cff6287899aa3b7755dea00d7362bfb52"
TEMPORAL_FP = "sha256:d557c0733cc59982c46f71efaa89dad03a27e0d0c6023ba54eb2ef807c84c570"
PACK_AUTH_NAME = "PRESIGNAL_V21_DESIGNED_DRIFT_2_NEW_R6_PACK_CONSTRUCTION_AUTHORIZATION_V1"


class RequestValidationError(ValueError):
    """A fail-closed Request payload validation result."""

    def __init__(self, code: str, divergences: list[str] | None = None):
        super().__init__(code)
        self.code = code
        self.divergences = divergences or [code]


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


def parse_utc(value: str) -> datetime:
    return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(timezone.utc)


def clean_text(value: Any) -> str:
    return " ".join(str(value or "").split())


def audit() -> dict[str, int]:
    return {
        "calendar_refreshes": 0, "apps_script_provider_bridge_executions": 0,
        "fmp_calls": 0, "google_reads": 0, "google_writes": 0,
        "gemini_calls": 0, "attention_calls": 0, "information_request_calls": 0,
        "acquisition_calls": 0, "forecast_calls": 0, "pack_a_constructions": 0,
        "pack_e_constructions": 0, "r6_evidence_writes": 0,
        "outcome_operations": 0, "evaluation_operations": 0,
    }


def selected_context() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    selected = read(SELECT / "new_r6_selected_episode_manifest.json")
    attention = read(SOURCE / "new_r6_native_attention.json")
    authorization = read(SOURCE / "new_r6_information_request_authorization_preparation.json")
    return selected, attention, authorization


def validate_authorization(selected: Mapping[str, Any], attention: Mapping[str, Any], authorization: Mapping[str, Any]) -> dict[str, Any]:
    computed = sha({key: value for key, value in authorization.items() if key != "authorization_fingerprint"})
    checks = {
        "authorization_name_valid": authorization.get("authorization_name") == "PRESIGNAL_V21_DESIGNED_DRIFT_2_NEW_R6_INFORMATION_REQUEST_CALL_AUTHORIZATION_V1",
        "authorization_fingerprint_valid": authorization.get("authorization_fingerprint") == AUTH_FP and computed == AUTH_FP,
        "authorization_prepared_not_activated": authorization.get("status") == "PREPARED_NOT_ACTIVATED" and authorization.get("authorization_activated") is False and authorization.get("request_call_executed") is False,
        "episode_selection_authorization_valid": sha(read(SELECT / "new_r6_episode_selection_authorization.json")) == SELECTION_FP,
        "episode_identity_valid": selected.get("episode_identity") == EPISODE == authorization.get("episode_identity"),
        "episode_checksums_valid": selected.get("content_checksum") == "sha256:e74f17bbd1e9b8a5cf6920c256f44a99decbf66af77dd716da81028611765143" and selected.get("provenance_checksum") == "sha256:feaafc5bbc1ceb88ca1500902b877eb572bb298e524312b131f0673127e9cfeb" and selected.get("lineage_checksum") == "sha256:d9400ea0ddb3848609ef00a10cc47aca234dce95cd195a2a1fd862fc8f675379",
        "attention_identity_valid": attention.get("attention_identity") == ATTENTION == authorization.get("attention_identity"),
        "attention_checksums_valid": attention.get("content_checksum") == authorization.get("attention_content_checksum") == "sha256:223025d1db8be393b8426fbca149ff19e77cc585328d97f61967116613a4ccbe" and attention.get("provenance_checksum") == authorization.get("attention_provenance_checksum") == "sha256:f3d72bce8d9f20065446c92aac5044f3e428921beb20cd4a6ce350d4d6c4da91" and attention.get("lineage_checksum") == authorization.get("attention_lineage_checksum") == "sha256:013be496bbbd13cf4bf61c04db77a931ba1da58e8eab4fc15c91cac87675a469",
        "attention_state_valid": attention.get("selection_state") == "SELECTED_FOR_INFORMATION_REQUESTS" and attention.get("acceptance_state") == "ACCEPTED",
        "provider_model_valid": authorization.get("provider") == PROVIDER and authorization.get("model") == MODEL,
        "prompt_version_valid": authorization.get("request_prompt_version") == PROMPT_VERSION == lineage.REQUEST_PROMPT_VERSION,
        "prompt_checksum_valid": authorization.get("request_prompt_checksum") == PROMPT_SHA == sha(lineage.REQUEST_INSTRUCTION),
        "category_enum_valid": authorization.get("category_enum_checksum") == CATEGORY_SHA == sha(sorted(lineage.VALID_CATEGORIES)),
        "temporal_alignment_valid": authorization.get("temporal_alignment_fingerprint") == TEMPORAL_FP,
        "call_budget_valid": authorization.get("call_budget") == 1,
        "retry_budget_valid": authorization.get("retry_count") == 0,
        "cutoff_valid": authorization.get("forecast_cutoff") == CUTOFF == selected.get("forecast_cutoff"),
    }
    return {"authorization_valid": all(checks.values()), "authorization_fingerprint": authorization.get("authorization_fingerprint"), "computed_authorization_fingerprint": computed, "checks": checks}


def build_pre_call(selected: Mapping[str, Any], attention: Mapping[str, Any], timestamp: str) -> dict[str, Any]:
    event_id = str(selected["primary_event_identity"])
    member = {"event_id": event_id, "batch_id": "", "type": "single", "indicator_name": selected["primary_event_name"], "genre": "Monetary Policy", "importance": "High", "release_ts": selected["release_timestamp"], "member_order": 1}
    attention_result = {"metadata": {"attention_run_id": ATTENTION}, "rows": [{"attention_run_id": ATTENTION, "session_id": EPISODE, "provider": PROVIDER, "model": MODEL, "status": "parsed", "event_id": event_id, "attention_label": "PRIMARY_DRIVER", "attention_rank": 1, "attention_reason": attention["selection_reason"], "expected_market_channel": "fed_path", "driver_role": "PRIMARY_DRIVER"}]}
    result = lineage.build_prospective_requests(
        study_id="PRESIGNAL_V21_R6", collection_run_id="R6_FOMC_INFORMATION_REQUEST_20260724",
        session_snapshot={"session_id": EPISODE, "country": selected["country"], "session_window_name": "R6_FOMC_RATE_DECISION", "session_start_ts": timestamp, "session_end_ts": CUTOFF},
        member_rows=[member], attention_result=attention_result, provider=PROVIDER, model=MODEL,
        information_cutoff_ts=CUTOFF, request_run_id="PRQ_" + sha({"episode": EPISODE, "attention": ATTENTION, "provider": PROVIDER})[7:27],
        stage_generated_ts=timestamp, instruction_override=lineage.REQUEST_INSTRUCTION, include_attention_identity=False,
    )
    if result.get("status") != "DRY_RUN":
        raise RuntimeError("REQUEST_PRE_CALL_CONSTRUCTION_FAILED")
    return {"bridge_request": result["request"], "prompt": result["prompt"], "request_run_id": result["metadata"]["request_run_id"], "member": member,
            "prompt_template_checksum": sha(lineage.REQUEST_INSTRUCTION), "resolved_prompt_checksum": sha(result["prompt"]),
            "response_schema_version": "v0", "response_schema_checksum": sha({"object": "session_information_requirements", "schema_version": "v0", "categories": sorted(lineage.VALID_CATEGORIES), "priorities": sorted(lineage.VALID_PRIORITIES), "channels": sorted(lineage.VALID_CHANNELS)}), "provider_call_parameters_checksum": sha(result["request"])}


def dispatch(request: Mapping[str, Any]) -> dict[str, Any]:
    credentials = google_clients.load_credentials(False, token_path=TOKEN, persist_refresh=False)
    service = google_clients.build_script_service(credentials, 240)
    result = google_clients.run_script_function_with_metadata(service, google_clients.default_script_id(), "apiCallAuthoritativeProviderJsonObject", [dict(request)])
    if not result.get("ok"):
        return {"status": "transport_failure", "transport": result}
    value = result.get("result")
    return dict(value) if isinstance(value, Mapping) else {"status": "provider_contract_error", "error": "BRIDGE_RESULT_NOT_OBJECT", "transport": result}


def content_flags(items: list[Mapping[str, Any]]) -> dict[str, bool]:
    text = " ".join(clean_text(item.get("requested_information")) + " " + clean_text(item.get("reason")) for item in items).lower()
    return {"forecast_content_detected": any(token in text for token in ("predict usd/jpy", "forecast usd/jpy direction", "pip magnitude", "5/15/30/60")),
            "post_release_content_detected": any(token in text for token in ("post-release", "post release", "react after", "reaction after", "released policy statement", "realized 15-minute", "realized 15 minute"))}


def temporal_error(requested_information: str) -> str | None:
    """Apply the frozen generic guard plus FOMC-specific clear future wording."""
    existing = lineage.validate_request_temporal_scope(requested_information)
    if existing:
        return existing
    text = clean_text(requested_information).lower()
    historical = any(marker in text for marker in ("historical", "previous", "prior ", "past ", "last "))
    if not historical and any(marker in text for marker in ("what rate did the fed announce", "what did the fed announce", "what rate will the fed announce", "released policy statement", "what did the policy statement say", "decision outcome")):
        return "REJECTED_PROMPT_PROHIBITED_RELEASED_ACTUAL_REFERENCE"
    return None


def normalize_response(raw_response: Any, transport: Mapping[str, Any], raw_checksum: str, *, authorization_fingerprint: str = AUTH_FP) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    if transport.get("actual_provider") != PROVIDER or transport.get("actual_model") != MODEL:
        raise RequestValidationError("REQUEST_TRANSPORT_PROVIDER_MODEL_MISMATCH")
    try:
        raw = json.loads(raw_response) if isinstance(raw_response, str) else dict(raw_response)
    except Exception as exc:
        raise RequestValidationError("REQUEST_RESPONSE_PARSE_INVALID") from exc
    if raw.get("object") != "session_information_requirements" or raw.get("status") != "ok":
        raise RequestValidationError("REQUEST_RESPONSE_SCHEMA_INVALID")
    items = raw.get("information_items")
    if not isinstance(items, list) or not items:
        raise RequestValidationError("REQUEST_RESPONSE_EMPTY" if items == [] else "REQUEST_RESPONSE_SCHEMA_INVALID")
    divergences: list[str] = []
    normalized_items: list[dict[str, Any]] = []
    seen: dict[str, dict[str, Any]] = {}
    seen_text_category: dict[str, str] = {}
    for index, item in enumerate(items, 1):
        if not isinstance(item, Mapping):
            divergences.append("REQUEST_ITEM_NOT_OBJECT"); continue
        category = clean_text(item.get("information_category"))
        requested = clean_text(item.get("requested_information"))
        reason = clean_text(item.get("reason"))
        priority = clean_text(item.get("priority"))
        channel = clean_text(item.get("affected_channel"))
        if category not in lineage.VALID_CATEGORIES:
            divergences.append("REQUEST_CATEGORY_INVALID:" + str(index)); continue
        if not requested or not reason or priority not in lineage.VALID_PRIORITIES or channel not in lineage.VALID_CHANNELS:
            divergences.append("REQUEST_ITEM_STRUCTURALLY_INCOMPLETE:" + str(index)); continue
        temporal = temporal_error(requested)
        if temporal:
            divergences.append(temporal + ":" + str(index)); continue
        key = sha({"category": category, "requested_information": requested})
        prior_category = seen_text_category.get(requested)
        if prior_category is not None and prior_category != category:
            divergences.append("REQUEST_CONFLICTING_DUPLICATE:" + str(index)); continue
        seen_text_category[requested] = category
        candidate = {"raw_rank": item.get("request_rank"), "information_category": category, "requested_information": requested, "reason": reason, "priority": priority, "affected_channel": channel,
                     "event_family_relevance": clean_text(item.get("event_family_relevance")), "linked_event_ids": [str(value) for value in item.get("linked_event_ids", [])] if isinstance(item.get("linked_event_ids"), list) else [],
                     "linked_attention_labels": [str(value) for value in item.get("linked_attention_labels", [])] if isinstance(item.get("linked_attention_labels"), list) else [], "available_now": item.get("available_now"),
                     "requested_source_identity": clean_text(item.get("suggested_source")) or None, "requested_source_role": "PREFERRED_RESEARCH_PROVIDER" if clean_text(item.get("suggested_source")) else None,
                     "requested_source_registry_status": "UNRESOLVED_NO_BOUND_AKSR_ENTRY" if clean_text(item.get("suggested_source")) else "NOT_SPECIFIED", "expected_forecast_use": clean_text(item.get("expected_forecast_use")), "is_market_state_candidate": item.get("is_market_state_candidate"), "temporal_classification": "HISTORICAL_CONTEXT_VALID" if any(marker in requested.lower() for marker in ("historical", "previous", "prior ", "past ", "last ")) else "PROSPECTIVE_PRE_RELEASE_VALID"}
        if key in seen:
            comparable = {name: value for name, value in candidate.items() if name != "raw_rank"}
            prior = {name: value for name, value in seen[key].items() if name != "raw_rank"}
            if comparable != prior:
                divergences.append("REQUEST_CONFLICTING_DUPLICATE:" + str(index))
            continue
        seen[key] = candidate
    if divergences:
        if any(value.startswith("REQUEST_CATEGORY_INVALID") for value in divergences):
            code = "REQUEST_CATEGORY_INVALID"
        elif any(value.startswith("REJECTED_PROMPT_") for value in divergences):
            code = "REQUEST_TEMPORAL_SCOPE_INVALID"
        else:
            code = "REQUEST_RESPONSE_SCHEMA_INVALID"
        raise RequestValidationError(code, divergences)
    normalized_items = sorted(seen.values(), key=lambda item: (int(item["raw_rank"]) if str(item["raw_rank"]).isdigit() else 999999, item["requested_information"], item["information_category"]))
    flags = content_flags(normalized_items)
    if any(flags.values()):
        raise RequestValidationError("REQUEST_TEMPORAL_SCOPE_INVALID", [key for key, value in flags.items() if value])
    normalized = {"object": "session_information_requirements", "schema_version": "v0", "canonical_provider_identity": PROVIDER, "transport_provider_identity": transport.get("actual_provider"), "transport_model_identity": transport.get("actual_model"), "episode_identity": EPISODE, "attention_identity": ATTENTION, "prompt_version": PROMPT_VERSION, "forecast_cutoff": CUTOFF, "raw_payload_provider_value": raw.get("provider"), "raw_payload_session_id": raw.get("session_id"), "untrusted_model_identity_fields": {key: raw.get(key) for key in ("provider", "session_id") if key in raw}, "unexpected_identity_fields_policy": "UNEXPECTED_FIELDS_IGNORED_NONAUTHORITATIVELY", "information_items": normalized_items, "raw_response_checksum": raw_checksum}
    normalized["normalized_response_checksum"] = sha({key: value for key, value in normalized.items() if key != "normalized_response_checksum"})
    rows: list[dict[str, Any]] = []
    for order, item in enumerate(normalized_items, 1):
        identity_basis = {"episode": EPISODE, "attention": ATTENTION, "provider": PROVIDER, "prompt": PROMPT_VERSION, "order": order, "category": item["information_category"], "requested": item["requested_information"]}
        request_identity = "NREQ_" + sha(identity_basis)[7:27]
        content = {"request_identity": request_identity, "episode_identity": EPISODE, "attention_identity": ATTENTION, "provider": PROVIDER, "model": MODEL, "information_category": item["information_category"], "requested_information": item["requested_information"], "reason": item["reason"], "priority": item["priority"], "affected_channel": item["affected_channel"], "requested_source_identity": item["requested_source_identity"], "requested_source_role": item["requested_source_role"], "requested_source_registry_status": item["requested_source_registry_status"], "temporal_classification": item["temporal_classification"], "canonical_order": order, "schema_version": "v0"}
        content_checksum = sha(content)
        provenance = {"raw_response_checksum": raw_checksum, "normalized_response_checksum": normalized["normalized_response_checksum"], "request_authorization_fingerprint": authorization_fingerprint, "attention_content_checksum": "sha256:223025d1db8be393b8426fbca149ff19e77cc585328d97f61967116613a4ccbe", "raw_payload_provider_value": raw.get("provider")}
        lineage_value = {"episode_identity": EPISODE, "attention_identity": ATTENTION, "provider": PROVIDER, "model": MODEL, "forecast_cutoff": CUTOFF, "prompt_checksum": PROMPT_SHA, "category_enum_checksum": CATEGORY_SHA, "temporal_alignment_fingerprint": TEMPORAL_FP, "canonical_order": order}
        rows.append({**content, "raw_information_category": item["information_category"], "request_text": item["requested_information"], "event_family_relevance": item["event_family_relevance"], "linked_event_ids": item["linked_event_ids"], "linked_attention_labels": item["linked_attention_labels"], "available_now": item["available_now"], "expected_forecast_use": item["expected_forecast_use"], "is_market_state_candidate": item["is_market_state_candidate"], "raw_response_checksum": raw_checksum, "normalized_response_checksum": normalized["normalized_response_checksum"], "content_checksum": content_checksum, "provenance": provenance, "provenance_checksum": sha(provenance), "lineage": lineage_value, "lineage_checksum": sha(lineage_value)})
    report = {"schema_valid": True, "request_count": len(rows), "raw_request_count": len(items), "canonical_request_count": len(rows), "duplicate_count": len(items) - len(rows), "category_validation": True, "temporal_validation": True, "provider_source_separation": True, "provider_identity_valid": True, "payload_source_roles": [row["requested_source_identity"] for row in rows], "raw_payload_provider_value": raw.get("provider"), "raw_payload_provider_treated_as_gemini_alias": False, "episode_match": True, "attention_match": True, "forecast_content_detected": flags["forecast_content_detected"], "post_release_content_detected": flags["post_release_content_detected"], "request_identities": [row["request_identity"] for row in rows], "request_set_checksum": sha(rows)}
    return normalized, rows, report


def pack_authorization(rows: list[Mapping[str, Any]], request_set_checksum: str, *, request_authorization_fingerprint: str = AUTH_FP) -> dict[str, Any]:
    value = {"authorization_name": PACK_AUTH_NAME, "status": "PREPARED_NOT_ACTIVATED", "episode_identity": EPISODE, "attention_identity": ATTENTION,
             "episode_selection_authorization_fingerprint": SELECTION_FP, "attention_content_checksum": "sha256:223025d1db8be393b8426fbca149ff19e77cc585328d97f61967116613a4ccbe", "attention_provenance_checksum": "sha256:f3d72bce8d9f20065446c92aac5044f3e428921beb20cd4a6ce350d4d6c4da91", "attention_lineage_checksum": "sha256:013be496bbbd13cf4bf61c04db77a931ba1da58e8eab4fc15c91cac87675a469", "request_authorization_fingerprint": request_authorization_fingerprint, "canonical_request_identities": [row["request_identity"] for row in rows], "request_set_checksum": request_set_checksum, "request_prompt_checksum": PROMPT_SHA, "category_enum_checksum": CATEGORY_SHA, "temporal_alignment_fingerprint": TEMPORAL_FP, "route_b_freeze_fingerprint": ROUTE_B_FREEZE, "forecast_cutoff": CUTOFF, "pack_a_scope": "selected provider ordered canonical Information Request set", "pack_e_scope": "shared approved market-state acquisition path", "authorization_activated": False, "pack_a_constructed": False, "pack_e_constructed": False, "forecast_calls": 0, "outcome_operations": 0, "evaluation_operations": 0}
    value["authorization_fingerprint"] = sha({key: item for key, item in value.items() if key != "authorization_fingerprint"})
    return value


def not_created(reason: str) -> dict[str, Any]:
    return {"status": "NOT_CREATED", "reason": reason}


def record_prior_transport_failure(*, at_utc: str | None = None, output: Path = OUT, error: str = "GOOGLE_OAUTH_TOKEN_MISSING") -> str:
    """Persist a pre-dispatch bridge failure without attempting a second call.

    This path is deliberately local-only.  It exists so that a failure while
    loading the accepted OAuth binding cannot tempt a retry merely to obtain
    normal evidence artifacts.
    """
    state = audit(); timestamp = at_utc or now()
    selected, attention, authorization = selected_context()
    validation = validate_authorization(selected, attention, authorization)
    pre = build_pre_call(selected, attention, timestamp)
    cutoff = {"call_timestamp_utc": timestamp, "forecast_cutoff_utc": CUTOFF, "time_remaining_seconds": (parse_utc(CUTOFF) - parse_utc(timestamp)).total_seconds(), "cutoff_open": parse_utc(timestamp) < parse_utc(CUTOFF)}
    envelope = {"episode_identity": EPISODE, "primary_event_identity": selected["primary_event_identity"], "primary_event_name": selected["primary_event_name"], "attention_identity": ATTENTION, "attention_lineage_checksum": attention["lineage_checksum"], "provider": PROVIDER, "model": MODEL, "request_prompt_version": PROMPT_VERSION, "request_prompt_checksum": PROMPT_SHA, "category_enum_checksum": CATEGORY_SHA, "temporal_alignment_fingerprint": TEMPORAL_FP, "forecast_cutoff": CUTOFF, "authorization_fingerprint": AUTH_FP, "request_timestamp": timestamp, "bridge_request": pre["bridge_request"]}
    reason = "REQUEST_TRANSPORT_FAILURE:" + error
    artifacts = {
        "new_r6_information_request_authorization_validation.json": {**validation, "authorization_activated": True, "authorization_consumed_after_attempt": True},
        "new_r6_information_request_envelope.json": envelope,
        "new_r6_information_request_request_checksum.json": {"request_content_checksum": sha({key: value for key, value in envelope.items() if key not in {"request_timestamp", "bridge_request"}}), "bridge_request_checksum": sha(pre["bridge_request"]), "resolved_prompt_checksum": pre["resolved_prompt_checksum"]},
        "new_r6_information_request_raw_response.json": {"raw_response": None, "raw_response_checksum": None, "preservation_status": "NOT_AVAILABLE_PRE_DISPATCH_TRANSPORT_FAILURE"},
        "new_r6_information_request_transport_report.json": {"status": "transport_failure_before_apps_script_execution", "error_classification": error, "requested_provider": PROVIDER, "requested_model": MODEL, "actual_provider": None, "actual_model": None, "http_status": None, "request_id": None, "finish_status": None, "usage": None, "apps_script_execution_attempted": False},
        "new_r6_information_request_schema_validation.json": {"schema_valid": False, "reason": reason, "all_detected_divergences": [reason], "first_deterministic_divergence": reason},
        "new_r6_information_request_category_validation.json": {"status": "NOT_EXECUTED_TRANSPORT_FAILURE"},
        "new_r6_information_request_temporal_validation.json": {"status": "NOT_EXECUTED_TRANSPORT_FAILURE"},
        "new_r6_information_request_provider_source_report.json": {"status": "NOT_EXECUTED_TRANSPORT_FAILURE"},
        "new_r6_information_request_normalized_response.json": not_created(reason),
        "new_r6_canonical_information_requests.json": not_created(reason),
        "new_r6_information_request_determinism_report.json": {"status": "NOT_EXECUTED_TRANSPORT_FAILURE"},
        "new_r6_pack_authorization_preparation.json": not_created(reason),
        "external_access_audit.json": state,
        "final_new_r6_information_request_decision.json": {"decision": "NEW_R6_INFORMATION_REQUEST_CALL_FAILED", "call_attempted": True, "provider_dispatch_attempts": 1, "gemini_call_count": 0, "apps_script_provider_bridge_executions": 0, "retries": 0, "pack_a_constructed": False, "pack_e_constructed": False},
    }
    for name, value in artifacts.items():
        write(output / name, value)
    return "NEW_R6_INFORMATION_REQUEST_CALL_FAILED"


def run(*, do_dispatch: bool, at_utc: str | None = None, output: Path = OUT) -> str:
    state = audit(); timestamp = at_utc or now()
    selected, attention, authorization = selected_context()
    validation = validate_authorization(selected, attention, authorization)
    cutoff = {"call_timestamp_utc": timestamp, "forecast_cutoff_utc": CUTOFF, "time_remaining_seconds": (parse_utc(CUTOFF) - parse_utc(timestamp)).total_seconds(), "cutoff_open": parse_utc(timestamp) < parse_utc(CUTOFF)}
    empty = {"new_r6_information_request_envelope.json": {"status": "NOT_EXECUTED"}, "new_r6_information_request_request_checksum.json": {"status": "NOT_CREATED"}, "new_r6_information_request_raw_response.json": {"status": "NOT_EXECUTED"}, "new_r6_information_request_transport_report.json": {"status": "NOT_EXECUTED"}, "new_r6_information_request_schema_validation.json": {"status": "NOT_EXECUTED"}, "new_r6_information_request_category_validation.json": {"status": "NOT_EXECUTED"}, "new_r6_information_request_temporal_validation.json": {"status": "NOT_EXECUTED"}, "new_r6_information_request_provider_source_report.json": {"status": "NOT_EXECUTED"}, "new_r6_information_request_normalized_response.json": not_created("NOT_EXECUTED"), "new_r6_canonical_information_requests.json": not_created("NOT_EXECUTED"), "new_r6_information_request_determinism_report.json": {"status": "NOT_EXECUTED"}, "new_r6_pack_authorization_preparation.json": not_created("NOT_EXECUTED")}
    if not validation["authorization_valid"]:
        decision = "NEW_R6_INFORMATION_REQUEST_BLOCKED_AUTHORIZATION_MISMATCH"; artifacts = empty
    elif not cutoff["cutoff_open"]:
        decision = "NEW_R6_INFORMATION_REQUEST_BLOCKED_CUTOFF_CLOSED"; artifacts = empty
    else:
        pre = build_pre_call(selected, attention, timestamp)
        envelope = {"episode_identity": EPISODE, "primary_event_identity": selected["primary_event_identity"], "primary_event_name": selected["primary_event_name"], "attention_identity": ATTENTION, "attention_lineage_checksum": attention["lineage_checksum"], "provider": PROVIDER, "model": MODEL, "request_prompt_version": PROMPT_VERSION, "request_prompt_checksum": PROMPT_SHA, "category_enum_checksum": CATEGORY_SHA, "temporal_alignment_fingerprint": TEMPORAL_FP, "forecast_cutoff": CUTOFF, "authorization_fingerprint": AUTH_FP, "request_timestamp": timestamp, "bridge_request": pre["bridge_request"]}
        if not do_dispatch:
            raise RuntimeError("DISPATCH_FLAG_REQUIRED")
        state["apps_script_provider_bridge_executions"] = 1; state["gemini_calls"] = 1; state["information_request_calls"] = 1
        response = dispatch(pre["bridge_request"])
        raw = response.get("raw_output")
        transport = {key: response.get(key) for key in ("status", "requested_provider", "requested_model", "actual_provider", "actual_model", "request_id", "request_status", "response_status", "terminal_status", "started_timestamp", "completed_timestamp", "prompt_tokens", "completion_tokens", "stop_reason", "error")}
        artifacts = {"new_r6_information_request_envelope.json": envelope, "new_r6_information_request_request_checksum.json": {"request_content_checksum": sha({key: value for key, value in envelope.items() if key not in {"request_timestamp", "bridge_request"}}), "bridge_request_checksum": sha(pre["bridge_request"]), "resolved_prompt_checksum": pre["resolved_prompt_checksum"]}, "new_r6_information_request_raw_response.json": {"raw_response": raw, "raw_response_checksum": sha(raw)}, "new_r6_information_request_transport_report.json": transport}
        try:
            if response.get("status") != "ok":
                raise RequestValidationError("REQUEST_TRANSPORT_FAILURE")
            normalized, rows, report = normalize_response(raw, response, sha(raw))
            runs = [normalize_response(raw, response, sha(raw))[1] for _ in range(3)]
            deterministic = len({sha(value) for value in runs}) == 1
            pack = pack_authorization(rows, report["request_set_checksum"])
            artifacts.update({"new_r6_information_request_schema_validation.json": {"schema_valid": True, "episode_identity_system_owned": EPISODE, "attention_identity_system_owned": ATTENTION, "model_identity_fields_ignored_non_authoritatively": list(normalized["untrusted_model_identity_fields"]), "all_detected_divergences": []}, "new_r6_information_request_category_validation.json": {"valid": True, "raw_categories": [item.get("information_category") for item in (json.loads(raw) if isinstance(raw, str) else raw)["information_items"]], "canonical_categories": [row["information_category"] for row in rows], "category_enum_checksum": CATEGORY_SHA}, "new_r6_information_request_temporal_validation.json": {"valid": True, "classifications": [row["temporal_classification"] for row in rows], "forecast_content_detected": report["forecast_content_detected"], "post_release_content_detected": report["post_release_content_detected"]}, "new_r6_information_request_provider_source_report.json": {"canonical_provider_identity": PROVIDER, "transport_model_identity": MODEL, "raw_payload_provider_value": normalized["raw_payload_provider_value"], "requested_sources": [row["requested_source_identity"] for row in rows], "payload_provider_treated_as_gemini_alias": False, "provider_source_separation_valid": True}, "new_r6_information_request_normalized_response.json": normalized, "new_r6_canonical_information_requests.json": {"requests": rows, "request_set_checksum": report["request_set_checksum"]}, "new_r6_information_request_determinism_report.json": {"runs": 3, "identical": deterministic, "request_identities": report["request_identities"], "request_set_checksum": report["request_set_checksum"]}, "new_r6_pack_authorization_preparation.json": pack})
            decision = "NEW_R6_INFORMATION_REQUEST_ACCEPTED_PACK_AUTHORIZATION_PREPARED"
        except RequestValidationError as exc:
            category = exc.code == "REQUEST_CATEGORY_INVALID"; temporal = exc.code == "REQUEST_TEMPORAL_SCOPE_INVALID"; provider_source = exc.code == "REQUEST_TRANSPORT_PROVIDER_MODEL_MISMATCH"
            decision = "NEW_R6_INFORMATION_REQUEST_CALL_FAILED" if exc.code == "REQUEST_TRANSPORT_FAILURE" else ("NEW_R6_INFORMATION_REQUEST_CATEGORY_INVALID" if category else ("NEW_R6_INFORMATION_REQUEST_TEMPORAL_SCOPE_INVALID" if temporal else ("NEW_R6_INFORMATION_REQUEST_PROVIDER_SOURCE_INVALID" if provider_source else "NEW_R6_INFORMATION_REQUEST_RESPONSE_INVALID")))
            artifacts.update({"new_r6_information_request_schema_validation.json": {"schema_valid": False, "all_detected_divergences": exc.divergences, "first_deterministic_divergence": exc.divergences[0]}, "new_r6_information_request_category_validation.json": {"valid": False, "reason": exc.code}, "new_r6_information_request_temporal_validation.json": {"valid": False, "reason": exc.code}, "new_r6_information_request_provider_source_report.json": {"status": "NOT_VALIDATED"}, "new_r6_information_request_normalized_response.json": not_created(exc.code), "new_r6_canonical_information_requests.json": not_created(exc.code), "new_r6_information_request_determinism_report.json": {"status": "NOT_EXECUTED_INVALID_RESPONSE"}, "new_r6_pack_authorization_preparation.json": not_created(exc.code)})
    artifacts["new_r6_information_request_authorization_validation.json"] = {**validation, "authorization_activated": state["gemini_calls"] == 1}
    artifacts["external_access_audit.json"] = state
    artifacts["final_new_r6_information_request_decision.json"] = {"decision": decision, "call_attempted": state["gemini_calls"] == 1, "call_count": state["gemini_calls"], "retries": 0, "pack_a_constructed": False, "pack_e_constructed": False}
    for name, value in artifacts.items():
        write(output / name, value)
    return decision


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--dispatch", action="store_true"); parser.add_argument("--record-prior-transport-failure", action="store_true"); parser.add_argument("--at-utc"); parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args()
    if args.dispatch and args.record_prior_transport_failure:
        parser.error("--dispatch and --record-prior-transport-failure are mutually exclusive")
    decision = record_prior_transport_failure(at_utc=args.at_utc, output=args.output) if args.record_prior_transport_failure else run(do_dispatch=args.dispatch, at_utc=args.at_utc, output=args.output)
    print(canonical({"decision": decision, "output": str(args.output.relative_to(ROOT))})); return 0


if __name__ == "__main__":
    raise SystemExit(main())
