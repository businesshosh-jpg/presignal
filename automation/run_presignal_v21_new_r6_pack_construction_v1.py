"""Bounded Pack A construction and Pack E source-environment gate for R6.

This runner deliberately contains no network, Google, provider, or forecast
client.  It freezes Pack A from the already canonical Request set, then
fails closed when the frozen Pack E capability has no prospective R6
approved-source environment bound to it.  In particular, an AKSR registry is
not substituted for the missing environment binding: that would silently
authorize a live acquisition route.
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

from automation import run_presignal_v21_new_r6_information_request_execution_v1 as request


PRIORITY = ROOT / "outputs/presignal_v21_designed_drift_r6_information_request_priority_contract_repair/R6-INFORMATION-REQUEST-PRIORITY-CONTRACT-REPAIR-20260724-v1"
SELECTION = ROOT / "outputs/presignal_v21_designed_drift_r6_episode_selection_fomc/R6-EPISODE-SELECTION-FOMC-20260724-v1"
ATTENTION = ROOT / "outputs/presignal_v21_designed_drift_r6_native_attention_field_ownership/R6-NATIVE-ATTENTION-FIELD-OWNERSHIP-20260724-v1"
OLD_R6_AUTH = ROOT / "outputs/presignal_v21_designed_drift_r6_authorization/R6-AUTH-20260723-gemini-paired-pack-a-e/r6_authorization_manifest.json"
OUT = ROOT / "outputs/presignal_v21_designed_drift_r6_pack_construction_fomc/R6-PACK-CONSTRUCTION-FOMC-20260724-v1"

EPISODE = "EP_EVENT_68a8e1cc3c9bf6ccc385"
ATTENTION_ID = "NATTN_013be496bbbd13cf4bf6"
CUTOFF = "2026-07-29T18:00:00Z"
PACK_AUTH_FP = "sha256:87fc65d0f9ec84e8efc1f0e8ef0276eb50a35d52c624191cc682dcea9f8fb869"
REQUEST_SET_FP = "sha256:8c068fdc3d9e5597e47160e8c279e74f708f19413d5f58bb15303241ac320844"
PRIORITY_CONTRACT_FP = "sha256:62720c3b8b86e9cd261db99c153401afdd97f4b54f96add9ce2fcaedc6caab74"
ROUTE_B_FP = "sha256:8c910a343515d88ca63ce4aaf738f28f9b4a8ab22665397077858bfaf7e866e4"


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
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_utc(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def audit(*, pack_a: int, pack_e: int) -> dict[str, int]:
    return {
        "approved_acquisition_calls": 0, "unapproved_acquisition_calls": 0,
        "calendar_refreshes": 0, "fmp_event_calendar_calls": 0,
        "google_reads": 0, "google_writes": 0,
        "gemini_attention_calls": 0, "gemini_information_request_calls": 0,
        "forecast_calls": 0, "pack_a_constructions": pack_a,
        "pack_e_constructions": pack_e, "r6_evidence_writes": 0,
        "outcome_operations": 0, "evaluation_operations": 0,
    }


def load_inputs() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    authorization = read(PRIORITY / "new_r6_pack_authorization_preparation.json")
    requests = read(PRIORITY / "new_r6_canonical_information_requests.json")
    episode = read(SELECTION / "new_r6_selected_episode_manifest.json")
    attention = read(ATTENTION / "new_r6_native_attention.json")
    old_r6_auth = read(OLD_R6_AUTH)
    return authorization, requests, episode, attention, old_r6_auth


def validate_authorization(authorization: Mapping[str, Any], requests: Mapping[str, Any], episode: Mapping[str, Any], attention: Mapping[str, Any]) -> dict[str, Any]:
    computed = sha({key: value for key, value in authorization.items() if key != "authorization_fingerprint"})
    request_rows = list(requests.get("requests") or [])
    expected_ids = [row.get("request_identity") for row in request_rows]
    checks = {
        "authorization_name": authorization.get("authorization_name") == "PRESIGNAL_V21_DESIGNED_DRIFT_2_NEW_R6_PACK_CONSTRUCTION_AUTHORIZATION_V1",
        "authorization_fingerprint": authorization.get("authorization_fingerprint") == PACK_AUTH_FP and computed == PACK_AUTH_FP,
        "prepared_not_activated": authorization.get("status") == "PREPARED_NOT_ACTIVATED" and authorization.get("authorization_activated") is False,
        "episode": authorization.get("episode_identity") == episode.get("episode_identity") == EPISODE,
        "attention": authorization.get("attention_identity") == attention.get("attention_identity") == ATTENTION_ID,
        "request_set": requests.get("request_set_checksum") == REQUEST_SET_FP == authorization.get("request_set_checksum"),
        "request_identities": expected_ids == authorization.get("canonical_request_identities") and len(expected_ids) == 10 and len(set(expected_ids)) == 10,
        "priority_contract": authorization.get("priority_contract_fingerprint") == PRIORITY_CONTRACT_FP,
        "route_b": authorization.get("route_b_freeze_fingerprint") == ROUTE_B_FP,
        "authorized_acquisition_boundary": authorization.get("pack_e_scope") == "shared approved market-state acquisition path",
        "cutoff": authorization.get("forecast_cutoff") == episode.get("forecast_cutoff") == CUTOFF,
        "request_contract": authorization.get("request_prompt_checksum") == request.PROMPT_SHA and authorization.get("category_enum_checksum") == request.CATEGORY_SHA and authorization.get("temporal_alignment_fingerprint") == request.TEMPORAL_FP,
    }
    return {"authorization_valid": all(checks.values()), "authorization_fingerprint": authorization.get("authorization_fingerprint"), "computed_authorization_fingerprint": computed, "checks": checks}


def construct_pack_a(rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    """Build Pack A only from the frozen canonical Requests, in their order."""
    ordered = [dict(row) for row in rows]
    if len(ordered) != 10 or any(row.get("canonical_order") != index for index, row in enumerate(ordered, 1)):
        raise ValueError("PACK_A_CANONICAL_REQUEST_ORDER_INVALID")
    if len({row.get("request_identity") for row in ordered}) != len(ordered):
        raise ValueError("PACK_A_DUPLICATE_REQUEST_IDENTITY")
    identity = {
        "pack_type": "PACK_A_SELECTED_PROVIDER_CANONICAL_REQUEST_SET",
        "episode_identity": EPISODE, "attention_identity": ATTENTION_ID,
        "provider": "Gemini", "model": "gemini-2.5-flash-lite",
        "request_set_checksum": REQUEST_SET_FP,
        "ordered_requests": ordered,
    }
    pack_id = "PACK_A_" + sha(identity)[7:31]
    lineage = {
        "episode_identity": EPISODE, "attention_identity": ATTENTION_ID,
        "request_set_checksum": REQUEST_SET_FP,
        "ordered_request_identities": [row["request_identity"] for row in ordered],
        "priority_contract_fingerprint": PRIORITY_CONTRACT_FP,
        "request_prompt_checksum": request.PROMPT_SHA,
        "category_enum_checksum": request.CATEGORY_SHA,
        "temporal_alignment_fingerprint": request.TEMPORAL_FP,
        "forecast_cutoff": CUTOFF,
    }
    provenance = {
        "construction": "direct deterministic materialization of selected provider ordered canonical Information Request set",
        "acquired_source_content_included": False,
        "shared_market_state_content_included": False,
        "request_content_checksums": [row["content_checksum"] for row in ordered],
    }
    return {
        "object": "CANONICAL_PACK_A", "pack_identity": pack_id,
        "pack_type": "PACK_A_SELECTED_PROVIDER_CANONICAL_REQUEST_SET",
        "episode_identity": EPISODE, "attention_identity": ATTENTION_ID,
        "provider": "Gemini", "model": "gemini-2.5-flash-lite",
        "forecast_cutoff": CUTOFF, "ordered_request_identities": lineage["ordered_request_identities"],
        "ordered_canonical_requests": ordered, "request_set_checksum": REQUEST_SET_FP,
        "priority_contract_fingerprint": PRIORITY_CONTRACT_FP,
        "request_prompt_checksum": request.PROMPT_SHA,
        "category_enum_checksum": request.CATEGORY_SHA,
        "temporal_alignment_fingerprint": request.TEMPORAL_FP,
        "content_checksum": sha(identity), "provenance": provenance,
        "provenance_checksum": sha(provenance), "lineage": lineage,
        "lineage_checksum": sha(lineage), "schema_version": "presignal_v21_pack_a_v1",
    }


def source_environment_gate(old_r6_auth: Mapping[str, Any]) -> dict[str, Any]:
    scope = dict(old_r6_auth.get("acquisition_scope") or {})
    environment = dict(scope.get("approved_source_environment") or {})
    unresolved = environment.get("authorization_status") == "UNRESOLVED"
    return {
        "authoritative_pack_e_builder": "automation/presignal_v21_pack_capability_v1.py:build_immutable_acquired_information_bundle -> assemble_canonical_pack_e",
        "pack_e_capability_mode": "return-only; caller supplies immutable acquisition records and a pre-bound approved-source environment",
        "registry_provenance": "git:e5a0ff288eb1f6fc228936cb1c693ed2bb2ab80f:automation/approved_knowledge_source_registry_v0.py",
        "historical_r6_authority_path": str(OLD_R6_AUTH.relative_to(ROOT)),
        "source_environment": environment,
        "source_environment_resolved_for_this_prospective_R6": not unresolved,
        "result": "BLOCKED_NO_PROSPECTIVE_R6_APPROVED_SOURCE_ENVIRONMENT" if unresolved else "RESOLVED",
        "why_registry_not_substituted": "The frozen historical R6 authority explicitly says that registry provenance does not itself bind an approved prospective R6 environment. Creating one here would add live acquisition authority.",
        "retry_budget": 0,
        "acquisition_dispatches_authorized": 0 if unresolved else None,
    }


def blank_pack_e_artifacts(gate: Mapping[str, Any]) -> dict[str, Any]:
    missing = [{"request_identity": request_id, "status": "NO_PACK_E_COVERAGE", "reason": "APPROVED_SOURCE_ENVIRONMENT_UNRESOLVED"} for request_id in [
        "NREQ_e601fe0e926ccf2d824a", "NREQ_4da74d4a74f993c02910", "NREQ_a90de3734b6ed432c17b", "NREQ_67a3086834b318fa1c6c", "NREQ_5b33c9c898bf70a1da54", "NREQ_e93a71ebc08e2feda8d9", "NREQ_775e4bd7bbe159b5f645", "NREQ_fb507464189df7132ad9", "NREQ_f22f9ec23a881e2fe306", "NREQ_b54d9d753ccc55a2cad6",
    ]]
    return {
        "new_r6_pack_e_acquisition_plan.json": {"status": "NOT_EXECUTED", "reason": gate["result"], "approved_source_environment": gate["source_environment"], "automatic_retries": 0, "unapproved_fallback_permitted": False},
        "new_r6_pack_e_acquisition_evidence.json": {"status": "NOT_EXECUTED", "operations": [], "approved_sources_attempted": 0, "successful_sources": 0, "failed_sources": 0, "unapproved_sources_used": 0, "automatic_retries": 0, "reason": gate["result"]},
        "new_r6_pack_e_temporal_validation.json": {"status": "NOT_EXECUTED", "reason": gate["result"], "post_release_content_detected": False},
        "new_r6_pack_e_source_approval_report.json": {"status": "BLOCKED", "approval_authority": gate["registry_provenance"], "approved_environment_bound": False, "unapproved_sources_used": 0, "reason": gate["result"]},
        "new_r6_pack_e_coverage_report.json": {"status": "NOT_CREATED", "reason": gate["result"], "coverage": missing},
        "new_r6_pack_e_missing_items_report.json": {"status": "ISSUED", "missing_items": missing, "frozen_pack_e_partial_construction_examined": True, "reason": "The builder can represent unavailable fields only after a caller supplies an authorized source environment; none is bound for this prospective R6."},
        "new_r6_pack_e.json": {"status": "NOT_CREATED", "reason": gate["result"]},
        "new_r6_pack_e_determinism_report.json": {"status": "NOT_EXECUTED", "reason": gate["result"]},
        "new_r6_pack_e_lineage_report.json": {"status": "NOT_CREATED", "reason": gate["result"]},
    }


def run(output: Path = OUT, current_utc: str | None = None) -> str:
    authorization, requests, episode, attention, old_r6_auth = load_inputs()
    current = current_utc or utc_now()
    validation = validate_authorization(authorization, requests, episode, attention)
    cutoff_open = parse_utc(current) < parse_utc(CUTOFF)
    cutoff = {"current_utc": current, "forecast_cutoff": CUTOFF, "cutoff_open": cutoff_open, "seconds_remaining": int((parse_utc(CUTOFF) - parse_utc(current)).total_seconds())}
    reports: dict[str, Any] = {
        "new_r6_pack_authorization_validation.json": validation,
        "new_r6_pack_cutoff_validation.json": cutoff,
    }
    reports["new_r6_pack_authorization_validation.json"]["authorization_activated_for_this_task"] = bool(validation["authorization_valid"] and cutoff_open)
    if not validation["authorization_valid"]:
        decision = "NEW_R6_PACK_CONSTRUCTION_BLOCKED_AUTHORIZATION_MISMATCH"
        reports.update({"new_r6_pack_a.json": {"status": "NOT_CREATED", "reason": decision}, "new_r6_pack_a_determinism_report.json": {"status": "NOT_EXECUTED"}, "new_r6_pack_a_lineage_report.json": {"status": "NOT_CREATED"}})
        gate = source_environment_gate(old_r6_auth); reports["new_r6_pack_e_source_registry_trace.json"] = gate; reports.update(blank_pack_e_artifacts(gate))
        reports["new_r6_pack_separation_report.json"] = {"status": "NOT_EXECUTED"}; reports["new_r6_paired_forecast_authorization_preparation.json"] = {"status": "NOT_CREATED"}; reports["new_r6_paired_forecast_authorization_fingerprint.json"] = {"status": "NOT_CREATED"}; reports["external_access_audit.json"] = audit(pack_a=0, pack_e=0)
    elif not cutoff_open:
        decision = "NEW_R6_PACK_CONSTRUCTION_BLOCKED_CUTOFF_CLOSED"
        reports.update({"new_r6_pack_a.json": {"status": "NOT_CREATED", "reason": decision}, "new_r6_pack_a_determinism_report.json": {"status": "NOT_EXECUTED"}, "new_r6_pack_a_lineage_report.json": {"status": "NOT_CREATED"}})
        gate = source_environment_gate(old_r6_auth); reports["new_r6_pack_e_source_registry_trace.json"] = gate; reports.update(blank_pack_e_artifacts(gate))
        reports["new_r6_pack_separation_report.json"] = {"status": "NOT_EXECUTED"}; reports["new_r6_paired_forecast_authorization_preparation.json"] = {"status": "NOT_CREATED"}; reports["new_r6_paired_forecast_authorization_fingerprint.json"] = {"status": "NOT_CREATED"}; reports["external_access_audit.json"] = audit(pack_a=0, pack_e=0)
    else:
        packs = [construct_pack_a(list(requests["requests"])) for _ in range(3)]
        pack_a = packs[0]
        reports["new_r6_pack_a.json"] = pack_a
        reports["new_r6_pack_a_determinism_report.json"] = {"runs": 3, "identical": len({sha(value) for value in packs}) == 1, "pack_identity": pack_a["pack_identity"], "content_checksum": pack_a["content_checksum"], "provenance_checksum": pack_a["provenance_checksum"], "lineage_checksum": pack_a["lineage_checksum"], "ordered_request_identities": pack_a["ordered_request_identities"]}
        reports["new_r6_pack_a_lineage_report.json"] = {"status": "PASS", "episode_identity": pack_a["episode_identity"], "attention_identity": pack_a["attention_identity"], "request_set_checksum": pack_a["request_set_checksum"], "request_count": len(pack_a["ordered_canonical_requests"]), "contains_acquired_source_content": False, "contains_pack_e_content": False}
        gate = source_environment_gate(old_r6_auth)
        reports["new_r6_pack_e_source_registry_trace.json"] = gate
        reports.update(blank_pack_e_artifacts(gate))
        reports["new_r6_pack_separation_report.json"] = {"status": "BLOCKED_BEFORE_PACK_E", "pack_a_type": pack_a["pack_type"], "pack_e_type": "NOT_CREATED", "identities_distinct": "NOT_EVALUABLE", "content_roles_distinct": "NOT_EVALUABLE", "episode_lineage_valid": True, "attention_lineage_valid": True, "request_lineage_valid": True, "reason": gate["result"]}
        reports["new_r6_paired_forecast_authorization_preparation.json"] = {"status": "NOT_CREATED", "reason": gate["result"], "authorization_activated": False, "forecast_calls": 0}
        reports["new_r6_paired_forecast_authorization_fingerprint.json"] = {"status": "NOT_CREATED", "reason": gate["result"]}
        reports["external_access_audit.json"] = audit(pack_a=1, pack_e=0)
        decision = "NEW_R6_PACK_E_ACQUISITION_BLOCKED"
    reports["final_new_r6_pack_construction_decision.json"] = {"decision": decision, "pack_authorization_activated": bool(validation["authorization_valid"] and cutoff_open), "pack_a_constructed": reports["new_r6_pack_a.json"].get("status") != "NOT_CREATED", "pack_e_constructed": False, "forecast_authorization_prepared": False, "forecast_calls": 0}
    for name, value in reports.items():
        write(output, name, value)
    return decision


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args()
    print(canonical({"decision": run(args.output), "output": str(args.output.relative_to(ROOT))}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
