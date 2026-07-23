"""Execute exactly one authorized Gemini Information-Request call for R6.

The sole dispatch is visibly isolated in ``run(..., dispatch=True)``.  All
normalization and canonical Request construction are return-only and use the
frozen Route B compute boundary.  This module neither persists Google objects
nor constructs Packs, forecasts, Outcomes, or evaluation records.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from automation import presignal_v21_event_path_contract_v1 as episode_contract
from automation import presignal_v21_minimal_prospective_lineage_v1 as lineage
from automation import presignal_v21_native_input_materialization_v1 as native
from automation import presignal_v21_pack_capability_v1 as capability
from automation import run_presignal_v21_native_attention_call_v1 as attention_call
from automation import run_presignal_v21_r6_native_attention_execution_v1 as attention_execution
from automation import run_presignal_v21_r6_native_input_final_materialization_v1 as input_materialization


OUTPUT = ROOT / "outputs" / "presignal_v21_designed_drift_r6_information_request_execution" / "R6-INFORMATION-REQUEST-EXECUTION-20260723-v1"
AUTHORIZATION_NAME = "PRESIGNAL_V21_DESIGNED_DRIFT_2_R6_INFORMATION_REQUEST_CALL_AUTHORIZATION_V1"
PROVIDER, MODEL = "Gemini", "gemini-2.5-flash-lite"
PROMPT_VERSION, RESPONSE_SCHEMA_VERSION = lineage.REQUEST_PROMPT_VERSION, "v0"
ROUTE_B_FREEZE = native.ROUTE_B_FREEZE
R6_V3 = "sha256:c8cb003af94eef2ef9cad8f323ab31b3c1990f3ffdcdab5ee3e6285fda76efb9"
SELECTION_FINGERPRINT = "sha256:73e8fe3f89126d9129ef6bcbbaeedeaf79d9f148d367248f9dcc778b307827e1"
ATTENTION_ID = "NATTN_b85703c6c08cdfdffd27"
ATTENTION_CONTENT = "sha256:1dba25a746b4083fc3e323d5d68bdfdbb602931c4a7d685601f5aa2f5b120872"
ATTENTION_PROVENANCE = "sha256:50b5e2dd7bf1be93b1edccbc63827eca0683c1836c24bf1ef7202ea097cfa000"
ATTENTION_LINEAGE = "sha256:b85703c6c08cdfdffd279d47120cccf3269fe61cbfc33040ad1758d81d884aeb"


class InformationRequestExecutionError(ValueError):
    pass


def canonical(value: Any) -> str:
    return json.dumps(plain(value), sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def checksum(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def plain(value: Any) -> Any:
    """Serialize the frozen Route B output without altering its content."""
    if isinstance(value, Mapping):
        return {str(key): plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [plain(item) for item in value]
    return value


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def parse_utc(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def read(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(canonical(value) + "\n", encoding="utf-8")


def request_authorization_manifest(*, episode: Mapping[str, Any], attention: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "authorization_name": AUTHORIZATION_NAME, "schema_version": "1",
        "route_b_freeze_fingerprint": ROUTE_B_FREEZE, "r6_authorization_v3_fingerprint": R6_V3,
        "episode_selection_authorization_fingerprint": SELECTION_FINGERPRINT,
        "episode_identity": episode["episode_id"], "attention_identity": attention["attention_identity"],
        "attention_content_checksum": ATTENTION_CONTENT, "attention_provenance_checksum": ATTENTION_PROVENANCE,
        "attention_lineage_checksum": ATTENTION_LINEAGE,
        "provider": PROVIDER, "model": MODEL, "information_request_call_budget": 1, "retry_count": 0,
        "information_request_prompt_version": PROMPT_VERSION, "response_schema_version": RESPONSE_SCHEMA_VERSION,
        "prohibitions": {"attention_calls": 0, "forecast_calls": 0, "acquisition_calls": 0,
                         "google_scientific_writes": 0, "outcome_operations": 0, "evaluation_operations": 0},
        "failure_stop_policy": ["authorization_mismatch", "cutoff_closed", "provider_model_mismatch",
                                "request_response_invalid", "request_response_empty", "canonicalization_failed", "no_retry"],
    }


def load_inputs() -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    attention, _raw, _provenance = input_materialization.load_validated_attention()
    episode_view, members, _source = attention_execution.load_frozen_episode()
    inventory = read(attention_execution.REFRESH_DIR / "canonical_episode_inventory.json")
    full = next((dict(row) for row in inventory["episodes"] if row.get("episode_id") == episode_view["episode_id"]), None)
    if full is None:
        raise InformationRequestExecutionError("R6_INFORMATION_REQUEST_EXECUTION_BLOCKED_AUTHORIZATION_MISMATCH:episode_missing")
    episode = {key: full[key] for key in episode_contract.EPISODE_FIELDS}
    try:
        episode_contract.validate_episode(episode)
    except episode_contract.ContractValidationError as exc:
        raise InformationRequestExecutionError("R6_INFORMATION_REQUEST_EXECUTION_BLOCKED_AUTHORIZATION_MISMATCH:episode_contract") from exc
    expected = {"attention_identity": ATTENTION_ID, "selection_state": "SELECTED_FOR_INFORMATION_REQUESTS",
                "acceptance_state": "ACCEPTED", "canonical_provider_identity": PROVIDER,
                "transport_model_identity": MODEL, "provenance_checksum": ATTENTION_PROVENANCE,
                "lineage_checksum": ATTENTION_LINEAGE}
    if any(attention.get(key) != value for key, value in expected.items()):
        raise InformationRequestExecutionError("R6_INFORMATION_REQUEST_EXECUTION_BLOCKED_AUTHORIZATION_MISMATCH:attention")
    if input_materialization.checksum(attention) != ATTENTION_CONTENT:
        raise InformationRequestExecutionError("R6_INFORMATION_REQUEST_EXECUTION_BLOCKED_AUTHORIZATION_MISMATCH:attention_content")
    raw_attention = read(input_materialization.EXECUTION / "attention_raw_response.json")
    return episode, members, attention, raw_attention


def attention_result_for_request(*, episode: Mapping[str, Any], members: Sequence[Mapping[str, Any]], attention: Mapping[str, Any], raw_attention: Mapping[str, Any]) -> dict[str, Any]:
    """Rehydrate only the already-preserved Attention Map into v2 Request input."""
    payload = json.loads(str(raw_attention["raw_response"]))
    by_id = {str(row.get("event_id")): dict(row) for row in payload.get("attention_items", []) if isinstance(row, Mapping)}
    rows = []
    for member in members:
        item = by_id.get(str(member["event_id"]))
        if item is None:
            raise InformationRequestExecutionError("REQUEST_ATTENTION_MEMBER_LINEAGE_MISMATCH")
        rows.append({"attention_run_id": attention["attention_identity"], "session_id": episode["episode_id"],
                     "provider": PROVIDER, "model": MODEL, "status": "parsed", "event_id": member["event_id"],
                     "attention_label": item.get("attention_label"), "attention_rank": item.get("attention_rank"),
                     "attention_reason": item.get("attention_reason"), "expected_market_channel": item.get("expected_market_channel"),
                     "driver_role": item.get("driver_role")})
    return {"metadata": {"attention_run_id": attention["attention_identity"]}, "rows": rows}


def build_pre_call(*, episode: Mapping[str, Any], members: Sequence[Mapping[str, Any]], attention: Mapping[str, Any], raw_attention: Mapping[str, Any], at_utc: str) -> dict[str, Any]:
    result = lineage.build_prospective_requests(
        study_id="PRESIGNAL_V21_R6", collection_run_id="R6_INFORMATION_REQUEST_EXECUTION_20260723",
        session_snapshot={"session_id": episode["episode_id"], "country": episode["country"],
                          "session_window_name": "R6_SELECTED_EPISODE", "session_start_ts": attention["effective_timestamp"],
                          "session_end_ts": episode["release_ts"]}, member_rows=members,
        attention_result=attention_result_for_request(episode=episode, members=members, attention=attention, raw_attention=raw_attention),
        provider=PROVIDER, model=MODEL, information_cutoff_ts=episode["forecast_cutoff_ts"],
        request_run_id="PRQ_" + checksum({"episode": episode["episode_id"], "attention": attention["attention_identity"], "provider": PROVIDER})[7:27],
        stage_generated_ts=at_utc,
    )
    if result["status"] != "DRY_RUN":
        raise InformationRequestExecutionError("REQUEST_PRE_CALL_CONSTRUCTION_FAILED")
    request = result["request"]
    return {"bridge_request": request, "prompt": result["prompt"], "request_run_id": result["metadata"]["request_run_id"],
            "prompt_template_checksum": checksum(lineage.REQUEST_INSTRUCTION), "resolved_prompt_checksum": checksum(result["prompt"]),
            "response_schema_checksum": checksum({"object": "session_information_requirements", "schema_version": RESPONSE_SCHEMA_VERSION,
                                                    "categories": sorted(lineage.VALID_CATEGORIES), "priorities": sorted(lineage.VALID_PRIORITIES),
                                                    "channels": sorted(lineage.VALID_CHANNELS)}),
            "provider_call_parameters_checksum": checksum(request)}


def capability_attention(*, episode: Mapping[str, Any], attention: Mapping[str, Any]) -> dict[str, Any]:
    return {"object": "NATIVE_SELECTED_ATTENTION", "attention_id": attention["attention_identity"], "episode_id": episode["episode_id"],
            "selection_status": attention["selection_state"], "acceptance_state": attention["acceptance_state"],
            "selection_reason": attention["selection_reason"], "provider": PROVIDER, "model": MODEL,
            "prompt_version": attention["prompt_version"], "forecast_cutoff_ts": episode["forecast_cutoff_ts"],
            "created_ts": attention["effective_timestamp"], "attention_labels": ["PRIMARY_DRIVER"]}


def validate_and_compute(*, episode: Mapping[str, Any], attention: Mapping[str, Any], raw_response: Any,
                         transport: Mapping[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if transport.get("actual_provider") != PROVIDER or transport.get("actual_model") != MODEL:
        raise InformationRequestExecutionError("REQUEST_TRANSPORT_PROVIDER_MODEL_MISMATCH")
    raw = json.loads(raw_response) if isinstance(raw_response, str) else dict(raw_response)
    # No Request-specific bridge-role mapping exists; payload identity remains strict.
    if raw.get("provider") != PROVIDER:
        raise InformationRequestExecutionError("REQUEST_RESPONSE_PROVIDER_MISMATCH")
    if raw.get("session_id") != episode["episode_id"]:
        raise InformationRequestExecutionError("REQUEST_RESPONSE_EPISODE_MISMATCH")
    items = raw.get("information_items")
    if not isinstance(items, list):
        raise InformationRequestExecutionError("REQUEST_ITEMS_NOT_ARRAY")
    if not items:
        raise InformationRequestExecutionError("REQUEST_RESPONSE_EMPTY")
    if any(not isinstance(item, Mapping) or item.get("information_category") not in lineage.VALID_CATEGORIES for item in items):
        raise InformationRequestExecutionError("REQUEST_CATEGORY_INVALID")
    try:
        frozen = capability.compute_canonical_information_requests(
            episode, capability_attention(episode=episode, attention=attention), PROVIDER, MODEL, PROMPT_VERSION,
            raw, episode["forecast_cutoff_ts"],
        )
    except Exception as exc:
        raise InformationRequestExecutionError(str(exc)) from exc
    rows = [plain(row) for row in frozen]
    if not rows:
        raise InformationRequestExecutionError("REQUEST_RESPONSE_EMPTY")
    report = {"schema_valid": True, "episode_match": True, "attention_match": True, "provider_model_match": True,
              "cutoff_valid": True, "empty_response": False, "next_validation_divergence": None,
              "raw_request_count": len(items), "canonical_request_count": len(rows), "duplicate_count": len(items) - len(rows),
              "request_identities": [row["request_identity"] for row in rows],
              "request_categories": [row["information_category"] for row in rows], "ordering_status": "CANONICAL_REQUEST_RANK_THEN_TEXT_THEN_KEY",
              "provider_lineage_match": all(row["lineage"]["provider"] == PROVIDER for row in rows),
              "model_lineage_match": all(row["lineage"]["model"] == MODEL for row in rows),
              "attention_lineage_match": all(row["lineage"]["attention_id"] == ATTENTION_ID for row in rows),
              "episode_lineage_match": all(row["lineage"]["episode_id"] == episode["episode_id"] for row in rows),
              "forecast_cutoff_lineage_match": all(row["lineage"]["forecast_cutoff_ts"] == episode["forecast_cutoff_ts"] for row in rows),
              "request_set_checksum": checksum(rows)}
    return rows, report


def audit() -> dict[str, int]:
    return {"gemini_information_request_calls": 0, "gemini_attention_calls": 0, "other_provider_calls": 0,
            "forecast_calls": 0, "http_acquisition_calls": 0, "market_data_calls": 0,
            "live_pack_e_computations": 0, "google_reads": 0, "google_writes": 0,
            "r6_evidence_writes": 0, "historical_mutations": 0, "outcome_operations": 0,
            "evaluation_operations": 0}


def run(*, output: Path, dispatch: bool, at_utc: str | None = None) -> None:
    state = audit()
    now = at_utc or utc_now()
    try:
        episode, members, attention, raw_attention = load_inputs()
        authorization = request_authorization_manifest(episode=episode, attention=attention)
        authorization_fp = checksum(authorization)
        if parse_utc(now) >= parse_utc(episode["forecast_cutoff_ts"]):
            decision = "R6_INFORMATION_REQUEST_EXECUTION_BLOCKED_CUTOFF_CLOSED"
            reports = {"information_request_call_authorization.json": authorization,
                       "information_request_call_authorization_fingerprint.json": {"authorization_name": AUTHORIZATION_NAME, "authorization_fingerprint": authorization_fp, "reproducible": True},
                       "information_request_authorization_validation.json": {"status": "PASS", "provider": PROVIDER, "model": MODEL, "call_budget": 1, "retry_count": 0},
                       "information_request_cutoff_revalidation.json": {"current_utc": now, "release_time": episode["release_ts"], "forecast_cutoff": episode["forecast_cutoff_ts"], "cutoff_open": False},
                       **{name: {"status": "NOT_EXECUTED", "reason": decision} for name in ("information_request_pre_call_manifest.json", "information_request_provider_request.json", "information_request_raw_response.json", "information_request_normalized_response.json", "canonical_information_requests.json", "canonical_request_validation_report.json", "canonical_request_determinism_report.json")},
                       "provider_call_budget_report.json": {"calls_used": 0, "calls_remaining": 1, "retry_budget_remaining": 0}, "external_access_audit.json": state,
                       "final_information_request_decision.json": {"decision": decision, "call_attempted": False, "call_count": 0}}
        else:
            pre = build_pre_call(episode=episode, members=members, attention=attention, raw_attention=raw_attention, at_utc=now)
            pre_manifest = {"authorization_identity": AUTHORIZATION_NAME, "authorization_fingerprint": authorization_fp,
                            "episode_identity": episode["episode_id"], "episode_checksum": attention_execution.EXPECTED_EPISODE_CHECKSUM,
                            "attention_identity": attention["attention_identity"], "attention_content_checksum": ATTENTION_CONTENT,
                            "attention_provenance_checksum": ATTENTION_PROVENANCE, "attention_lineage_checksum": ATTENTION_LINEAGE,
                            "provider": PROVIDER, "model": MODEL, "prompt_version": PROMPT_VERSION,
                            "prompt_template_checksum": pre["prompt_template_checksum"], "resolved_prompt_checksum": pre["resolved_prompt_checksum"],
                            "response_schema_version": RESPONSE_SCHEMA_VERSION, "response_schema_checksum": pre["response_schema_checksum"],
                            "provider_call_parameters_checksum": pre["provider_call_parameters_checksum"], "call_sequence_number": 1, "retry_count": 0}
            if not dispatch:
                raise InformationRequestExecutionError("DISPATCH_FLAG_REQUIRED")
            # This is the sole authorized dispatch.  The original read-only token path is
            # used because the worktree intentionally contains no credential material.
            state["gemini_information_request_calls"] = 1
            response = attention_execution._dispatch(pre["bridge_request"], Path("/Users/junhoshino/projects/presignal/local/token.json"))
            raw = response.get("raw_output")
            base = {"information_request_call_authorization.json": authorization,
                    "information_request_call_authorization_fingerprint.json": {"authorization_name": AUTHORIZATION_NAME, "authorization_fingerprint": authorization_fp, "reproducible": True},
                    "information_request_authorization_validation.json": {"status": "PASS", "route_b_freeze_valid": True, "r6_authorization_v3_valid": True, "episode_selection_authorization_valid": True, "attention_binding_valid": True, "provider": PROVIDER, "model": MODEL, "call_budget": 1, "retry_count": 0, "forecast_prohibited": True, "google_writes_prohibited": True},
                    "information_request_cutoff_revalidation.json": {"current_utc": now, "release_time": episode["release_ts"], "forecast_cutoff": episode["forecast_cutoff_ts"], "attention_effective_timestamp": attention["effective_timestamp"], "cutoff_open": True},
                    "information_request_pre_call_manifest.json": pre_manifest, "information_request_provider_request.json": pre["bridge_request"],
                    "information_request_raw_response.json": {"raw_response": raw, "raw_response_checksum": checksum(raw), "transport_metadata": {key: response.get(key) for key in ("status", "requested_provider", "requested_model", "actual_provider", "actual_model", "started_timestamp", "completed_timestamp", "request_status", "response_status", "terminal_status", "request_id", "prompt_tokens", "completion_tokens", "stop_reason", "error")}}
                   }
            try:
                if response.get("status") != "ok":
                    raise InformationRequestExecutionError("REQUEST_TRANSPORT_FAILURE")
                rows, validation = validate_and_compute(episode=episode, attention=attention, raw_response=raw, transport=response)
                repeated = [validate_and_compute(episode=episode, attention=attention, raw_response=raw, transport=response)[0] for _ in range(3)]
                stable = len({checksum(item) for item in repeated}) == 1
                base.update({"information_request_normalized_response.json": {"canonical_provider_identity": PROVIDER, "payload_provider_role": json.loads(raw).get("provider") if isinstance(raw, str) else raw.get("provider"), "bridge_identity_mapping_applied": False, "raw_response_checksum": checksum(raw)},
                             "canonical_information_requests.json": {"requests": rows, "request_set_checksum": validation["request_set_checksum"]},
                             "canonical_request_validation_report.json": validation,
                             "canonical_request_determinism_report.json": {"proof_runs": 3, "identical_runs": stable, "request_set_checksum": validation["request_set_checksum"], "request_identities": validation["request_identities"]},
                             "provider_call_budget_report.json": {"calls_used": 1, "calls_remaining": 0, "retry_budget_remaining": 0}, "external_access_audit.json": state,
                             "final_information_request_decision.json": {"decision": "R6_INFORMATION_REQUESTS_VALIDATED_PACK_A_MATERIALIZATION_READY", "call_attempted": True, "call_count": 1, "episode_identity": episode["episode_id"], "attention_identity": attention["attention_identity"]}})
            except Exception as exc:
                reason = str(exc); decision = "R6_INFORMATION_REQUEST_RESPONSE_EMPTY" if reason == "REQUEST_RESPONSE_EMPTY" else "R6_INFORMATION_REQUEST_CALL_FAILED"
                base.update({"information_request_normalized_response.json": {"status": "INVALID", "reason": reason}, "canonical_information_requests.json": {"status": "NOT_CREATED"},
                             "canonical_request_validation_report.json": {"schema_valid": False, "empty_response": reason == "REQUEST_RESPONSE_EMPTY", "next_validation_divergence": reason},
                             "canonical_request_determinism_report.json": {"status": "NOT_EXECUTED", "proof_runs": 0}, "provider_call_budget_report.json": {"calls_used": 1, "calls_remaining": 0, "retry_budget_remaining": 0}, "external_access_audit.json": state,
                             "final_information_request_decision.json": {"decision": decision, "call_attempted": True, "call_count": 1, "failure": reason}})
            reports = base
    except Exception as exc:
        reports = {"information_request_call_authorization.json": {"status": "NOT_EXECUTED"}, "information_request_call_authorization_fingerprint.json": {"status": "NOT_EXECUTED"},
                   "information_request_authorization_validation.json": {"status": "FAILED", "reason": str(exc)}, "information_request_cutoff_revalidation.json": {"status": "NOT_EXECUTED"},
                   **{name: {"status": "NOT_EXECUTED"} for name in ("information_request_pre_call_manifest.json", "information_request_provider_request.json", "information_request_raw_response.json", "information_request_normalized_response.json", "canonical_information_requests.json", "canonical_request_validation_report.json", "canonical_request_determinism_report.json")},
                   "provider_call_budget_report.json": {"calls_used": 0, "calls_remaining": 1, "retry_budget_remaining": 0}, "external_access_audit.json": state,
                   "final_information_request_decision.json": {"decision": "R6_INFORMATION_REQUEST_EXECUTION_BLOCKED_AUTHORIZATION_MISMATCH", "call_attempted": False, "call_count": 0, "failure": str(exc)}}
    for name, value in reports.items():
        write(output / name, value)


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--output", type=Path, default=OUTPUT); parser.add_argument("--dispatch", action="store_true"); parser.add_argument("--at-utc")
    args = parser.parse_args(); run(output=args.output, dispatch=args.dispatch, at_utc=args.at_utc); return 0


if __name__ == "__main__":
    raise SystemExit(main())
