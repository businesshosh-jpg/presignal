#!/usr/bin/env python3
"""Adapt frozen v2 information artifacts to v2.1 Episode forecast-ready inputs.

This module is deliberately a reader and compatibility boundary.  It never
dispatches providers, acquires information, or writes workbooks.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from automation.build_simplified_replay_package_v1 import verify_package_manifest, verify_whole_package_fingerprint

EPISODES = ROOT / "outputs" / "presignal_v21_episode_builder" / "episode_rows.jsonl"
ROLES = ROOT / "outputs" / "presignal_v21_episode_outcomes" / "episode_component_roles.jsonl"
PACKAGE = ROOT / "outputs" / "simplified_authoritative_replay" / "production_packages" / "SIMPLIFIED-REPLAY-PROD-20260718T010455Z"
OUTPUT = ROOT / "outputs" / "presignal_v21_step5_reuse"
SYSTEM_VERSION = "presignal_v2.1"
SCHEMA_VERSION = "2.1.0"
HORIZONS = [5, 15, 30, 60]
PACK_A_ID = "PACK_A_NO_SHARED_MARKET_STATE_PACK"
PACK_A_VERSION = "historical_square_one_no_shared_pack_a"
ATTENTION_TO_SELECTION = {
    "PRIMARY_DRIVER": "FORECAST", "SECONDARY_DRIVER": "WATCH", "WATCHLIST": "WATCH",
    "CONTEXT_ONLY": "WATCH", "IGNORE": "IGNORE", "NO_SIGNAL": "NO_SIGNAL",
}
UNAVAILABLE = {
    "NO_EXACT_PARENT_SESSION", "MULTIPLE_PARENT_SESSIONS", "ATTENTION_MAP_MISSING",
    "ATTENTION_LINEAGE_MISMATCH", "INFORMATION_REQUESTS_MISSING", "REQUEST_LINEAGE_MISMATCH",
    "PACK_A_MISSING", "PACK_E_MISSING", "PACK_FINGERPRINT_MISMATCH", "CUTOFF_MISMATCH",
    "POST_CUTOFF_SOURCE", "UNSUPPORTED_LEGACY_SCHEMA",
}
FORBIDDEN_INPUT_FIELDS = {
    "outcome_id", "outcome_fingerprint", "evaluation_id", "evaluation_fingerprint", "released_value",
    "actual_value", "anchor_price", "anchor_price_ts", "price_5m", "price_15m", "price_30m",
    "price_60m", "pips_5m", "pips_15m", "pips_30m", "pips_60m", "max_up_pips",
    "max_down_pips", "max_up_ts", "max_down_ts", "reversal_flag", "reversal_ts",
    "final_usdjpy_direction", "previous_forecast_answer", "prediction_answer",
}


class CompatibilityError(ValueError):
    pass


def canon(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, default=str)


def fingerprint(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canon(value).encode()).hexdigest()


def rows(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def write_jsonl(path: Path, values: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(canon(value) + "\n" for value in values))


def utc(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def inventory() -> list[dict[str, Any]]:
    entries = [
        ("Market Session identity and membership", "snapshot/authoritative_sessions.jsonl; snapshot/authoritative_session_members.jsonl", "load_frozen_package", "Market Session", "exact session membership", True, False, ""),
        ("Session Attention Map capture", "frozen package attention export", "read_attention_records", "Session member", "member attention", False, True, "authoritative package has no attention export"),
        ("Attention parsing and validation", "frozen v2 attention parser", "parse_attention_records", "provider raw attention", "attention labels", False, True, "implementation not present in current repository"),
        ("Session Information Request capture", "snapshot/authoritative_requests.jsonl", "load_frozen_package", "Market Session/provider", "normalized requests", True, True, ""),
        ("Request normalization", "snapshot/authoritative_requests.jsonl.normalized_information_key", "read normalized request rows", "request wording", "normalized key", True, True, "source normalizer module absent; frozen normalized output is preserved"),
        ("Information Requirement handling", "snapshot/authoritative_requests.jsonl", "read normalized request rows", "provider request", "requirement lineage", True, True, ""),
        ("Request fulfillment classification", "snapshot/authoritative_pack_references.jsonl.items", "read shared pack", "normalized request", "item status", True, True, ""),
        ("Deterministic and computed acquisition", "snapshot/authoritative_pack_references.jsonl.items", "read shared pack", "request", "acquisition/source lineage", True, True, ""),
        ("Permitted provisional acquisition", "snapshot/authoritative_pack_references.jsonl.items", "read shared pack", "request", "provisional label", True, True, ""),
        ("Shared Pack construction", "snapshot/authoritative_pack_references.jsonl", "read shared pack", "session requests", "shared Pack E", True, True, ""),
        ("Pack A and Pack E definitions", "assignments/pack_assignments.jsonl; snapshot/authoritative_pack_references.jsonl", "load_frozen_package", "session/provider", "Pack A/E identity", True, True, ""),
        ("Cutoff and historical as-of validation", "snapshot/authoritative_sessions.jsonl; authoritative_pack_references.jsonl", "validate_cutoff_and_pack", "session/pack", "leakage-safe lineage", True, True, ""),
        ("Source and provenance validation", "automation/build_simplified_replay_package_v1.py", "verify_package_manifest; verify_whole_package_fingerprint", "frozen package", "verified reader", True, False, ""),
        ("Provider/model adapters", "assignments/provider_model_assignments.jsonl", "load_frozen_package", "session/provider", "provider/model", True, True, ""),
        ("Retry, timeout, duplicate, terminal controls", "automation/run_phase9_authoritative_historical_replay_v0.py", "PackageState/reconcile_completion", "forecast identity", "terminal ledger", True, False, "not invoked by Step 5"),
        ("Frozen historical artifact readers", "automation/build_simplified_replay_package_v1.py", "verify_package_manifest; verify_whole_package_fingerprint", "package", "verified snapshot", True, False, ""),
        ("Prospective collection interfaces", "v2 prospective output contract", "adapt_prospective_outputs", "v2 output records", "Episode inputs", False, True, "live v2 entrypoints are not present locally"),
    ]
    return [dict(zip(("component", "existing_implementation_path", "existing_callable_entrypoint", "current_input_identity", "current_output_identity", "reusable_as_is", "requires_narrow_episode_adapter", "concrete_incompatibility"), entry), minimal_repair_required=("export exact frozen attention records" if entry[-1] == "authoritative package has no attention export" else "restore/bind existing v2 callable without semantic change" if entry[-1] else "")) for entry in entries]


def load_frozen_package(package: Path = PACKAGE, attention_artifact: Path | None = None) -> dict[str, Any]:
    if not verify_package_manifest(package) or not verify_whole_package_fingerprint(package):
        raise CompatibilityError("FROZEN_PACKAGE_FINGERPRINT_MISMATCH")
    snapshot = package / "snapshot"
    packaged_attention = snapshot / "authoritative_attention_map.jsonl"
    attention_path = attention_artifact or packaged_attention
    state = {
        "package": package.name,
        "sessions": rows(snapshot / "authoritative_sessions.jsonl"),
        "members": rows(snapshot / "authoritative_session_members.jsonl"),
        "requests": rows(snapshot / "authoritative_requests.jsonl"),
        "packs": rows(snapshot / "authoritative_pack_references.jsonl"),
        "assignments": rows(package / "assignments" / "pack_assignments.jsonl"),
        "providers": rows(package / "assignments" / "provider_model_assignments.jsonl"),
        "attention": rows(attention_path) if attention_path.exists() else [],
        "attention_available": attention_path.exists(),
        "attention_artifact": str(attention_path) if attention_path.exists() else "",
    }
    state["sessions_by_id"] = {row["session_id"]: row for row in state["sessions"]}
    state["members_by_session"] = defaultdict(list)
    for row in state["members"]:
        state["members_by_session"][row["session_id"]].append(row)
    state["requests_by_session"] = defaultdict(list)
    for row in state["requests"]:
        state["requests_by_session"][row["session_id"]].append(row)
    state["pack_by_session"] = {row["session_id"]: row for row in state["packs"]}
    return state


def usable_attention(row: Mapping[str, Any]) -> bool:
    """Only original successful classifications may select a v2.1 Episode."""
    return (
        row.get("status") == "parsed"
        and row.get("attention_label") in ATTENTION_TO_SELECTION
        and row.get("step5_lineage_status", "VALID_FOR_STEP5") == "VALID_FOR_STEP5"
    )


def select_status(labels: Iterable[str]) -> str:
    labels = set(labels)
    if "PRIMARY_DRIVER" in labels: return "FORECAST"
    if labels & {"SECONDARY_DRIVER", "WATCHLIST", "CONTEXT_ONLY"}: return "WATCH"
    if "NO_SIGNAL" in labels: return "NO_SIGNAL"
    if labels and labels <= {"IGNORE"}: return "IGNORE"
    return "UNAVAILABLE"


def parent_session(episode: Mapping[str, Any], state: Mapping[str, Any]) -> tuple[str | None, str | None]:
    release = utc(episode["release_ts"])
    candidates = []
    for session in state["sessions"]:
        if session["country"] != episode["country"] or not (utc(session["session_start_ts"]) <= release <= utc(session["session_end_ts"])):
            continue
        member_index = defaultdict(list)
        for member in state["members_by_session"][session["session_id"]]:
            member_index[member["event_id"]].append(member)
        if all(any(utc(member["release_ts"]) == release for member in member_index[event_id]) for event_id in episode["member_event_ids"]):
            candidates.append(session["session_id"])
    if len(candidates) == 1: return candidates[0], None
    return None, "NO_EXACT_PARENT_SESSION" if not candidates else "MULTIPLE_PARENT_SESSIONS"


def validate_cutoff_and_pack(session: Mapping[str, Any], pack: Mapping[str, Any], release_ts: str) -> str | None:
    cutoff, release = utc(session["forecast_cutoff"]), utc(release_ts)
    if cutoff > release or pack.get("forecast_cutoff") != session.get("forecast_cutoff"):
        return "CUTOFF_MISMATCH"
    for item in pack.get("items", []):
        if item.get("forecast_cutoff") != session.get("forecast_cutoff"):
            return "CUTOFF_MISMATCH"
        for key in ("source_timestamp", "historical_availability_timestamp", "observation_timestamp"):
            value = item.get(key)
            if value and utc(value) > cutoff:
                return "POST_CUTOFF_SOURCE"
    return None


def reject_leakage(value: Any) -> None:
    if isinstance(value, Mapping):
        for key, nested in value.items():
            if key in FORBIDDEN_INPUT_FIELDS:
                raise CompatibilityError("FORBIDDEN_LEAKAGE_FIELD:" + key)
            reject_leakage(nested)
    elif isinstance(value, list):
        for nested in value: reject_leakage(nested)


def structural_members(episode: Mapping[str, Any], roles_by_episode: Mapping[str, list[Mapping[str, Any]]]) -> list[dict[str, Any]]:
    by_event = {row["event_id"]: row for row in roles_by_episode[episode["episode_id"]]}
    return [{"event_id": event_id, "indicator_name": indicator, "structural_component_role": by_event[event_id]["component_role"]} for event_id, indicator in zip(episode["member_event_ids"], episode["member_indicator_names"])]


def build_episode_inputs(episodes: list[Mapping[str, Any]], state: Mapping[str, Any], roles: list[Mapping[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    roles_by_episode = defaultdict(list)
    for role in roles: roles_by_episode[role["episode_id"]].append(role)
    parent_rows=[]; attention_rows=[]; request_rows=[]; pack_rows=[]; unavailable=[]; inputs_a=[]; inputs_e=[]
    for episode in sorted(episodes, key=lambda row: row["episode_id"]):
        episode_id = episode["episode_id"]; session_id, parent_reason = parent_session(episode, state)
        parent_rows.append({"episode_id": episode_id, "source_session_id": session_id or "", "status": "MATCHED" if session_id else "UNAVAILABLE", "reason": parent_reason or "", "release_ts": episode["release_ts"], "member_event_ids": episode["member_event_ids"]})
        reasons=[] if session_id else [parent_reason]
        if not session_id:
            attention_rows.append({"episode_id": episode_id, "status":"UNAVAILABLE", "reason":parent_reason, "records":[]}); request_rows.append({"episode_id":episode_id,"status":"UNAVAILABLE","reason":parent_reason,"requests":[]}); pack_rows.append({"episode_id":episode_id,"status":"UNAVAILABLE","reason":parent_reason}); unavailable.append({"episode_id":episode_id,"reasons":reasons}); continue
        session=state["sessions_by_id"][session_id]; pack=state["pack_by_session"].get(session_id)
        cutoff_reason = validate_cutoff_and_pack(session, pack, episode["release_ts"]) if pack else "PACK_E_MISSING"
        attention = [row for row in state["attention"] if row.get("session_id") == session_id]
        usable = [row for row in attention if usable_attention(row)]
        if not attention:
            reasons.append("ATTENTION_MAP_MISSING")
            attention_rows.append({"episode_id":episode_id,"source_session_id":session_id,"status":"UNAVAILABLE","reason":"ATTENTION_MAP_MISSING","records":[]})
        else:
            selected=[]
            for provider_model in sorted({(row.get("provider"),row.get("model")) for row in attention}):
                records=[row for row in usable if (row.get("provider"),row.get("model"))==provider_model and row.get("event_id") in episode["member_event_ids"]]
                selected.append({"provider":provider_model[0],"model":provider_model[1],"provider_episode_selection":select_status(row.get("attention_label","") for row in records),"member_attention_records":records})
            compatible = any(item["provider_episode_selection"] != "UNAVAILABLE" for item in selected)
            if not compatible:
                reasons.append("ATTENTION_LINEAGE_MISMATCH")
            attention_rows.append({"episode_id":episode_id,"source_session_id":session_id,"status":"COMPATIBLE" if compatible else "UNAVAILABLE","reason":"" if compatible else "ATTENTION_LINEAGE_MISMATCH","records":selected})
        request_group=defaultdict(list)
        for row in state["requests_by_session"].get(session_id,[]): request_group[(row["provider"],row["model"])].append(row)
        request_rows.append({"episode_id":episode_id,"source_session_id":session_id,"status":"COMPATIBLE" if request_group else "UNAVAILABLE","reason":"" if request_group else "INFORMATION_REQUESTS_MISSING","provider_request_counts":{f"{p}|{m}":len(v) for (p,m),v in sorted(request_group.items())}})
        if not request_group: reasons.append("INFORMATION_REQUESTS_MISSING")
        if cutoff_reason: reasons.append(cutoff_reason)
        provider_arms=defaultdict(set)
        for assignment in state["assignments"]: provider_arms[(assignment["session_id"], assignment.get("forecast_identity",""))].add(assignment["pack_arm"])
        # The frozen forecast population supplies the provider/model identity for each arm.
        frozen_identities = rows(PACKAGE / "snapshot" / "authoritative_forecast_population.jsonl")
        pairs=defaultdict(set)
        for identity in frozen_identities:
            if identity["session_id"]==session_id: pairs[(identity["provider"],identity["model"])].add(identity["arm"])
        valid_pairs=[key for key, arms in pairs.items() if arms=={"A","E"}]
        pack_rows.append({"episode_id":episode_id,"source_session_id":session_id,"status":"COMPATIBLE" if pack and valid_pairs and not cutoff_reason else "UNAVAILABLE","reason":cutoff_reason or ("PACK_A_MISSING" if not valid_pairs else ""),"provider_model_pairs":[f"{p}|{m}" for p,m in sorted(valid_pairs)],"pack_e_fingerprint":pack.get("pack_fingerprint","") if pack else ""})
        if not valid_pairs: reasons.append("PACK_A_MISSING")
        if not pack: reasons.append("PACK_E_MISSING")
        if reasons:
            unavailable.append({"episode_id":episode_id,"source_session_id":session_id,"reasons":sorted(set(reasons))}); continue
        attention_by_provider={(item["provider"],item["model"]):item for item in attention_rows[-1]["records"]}
        for provider, model in sorted(valid_pairs):
            attention_item=attention_by_provider.get((provider,model))
            if not attention_item or attention_item["provider_episode_selection"]=="UNAVAILABLE":
                unavailable.append({"episode_id":episode_id,"source_session_id":session_id,"provider":provider,"model":model,"reasons":["ATTENTION_LINEAGE_MISMATCH"]}); continue
            base={"object":"event_path_forecast_input","system_version":SYSTEM_VERSION,"schema_version":SCHEMA_VERSION,"episode_id":episode_id,"source_session_id":session_id,"country":episode["country"],"release_ts":episode["release_ts"],"forecast_cutoff_ts":session["forecast_cutoff"],"episode_members":structural_members(episode,roles_by_episode),"structural_component_roles":structural_members(episode,roles_by_episode),"provider_attention_map":attention_item["member_attention_records"],"provider_episode_selection":attention_item["provider_episode_selection"],"information_requests":request_group[(provider,model)],"provider":provider,"model":model,"target":"EPISODE_EVENT_PATH","horizons_min":HORIZONS,"prompt_version_placeholder":"STEP_6_FROZEN_PROMPT_NOT_YET_BOUND","future_outcome_identity_basis":{"episode_id":episode_id,"release_ts":episode["release_ts"],"horizons_min":HORIZONS},"lineage":{"source_session_id":session_id,"pack_e_fingerprint":pack["pack_fingerprint"],"frozen_package":state["package"]}}
            for arm, shared in (("PACK_A",None),("PACK_E",pack)):
                item={**base,"information_arm":arm,"shared_market_state_pack":shared,"pack_id":PACK_A_ID if arm=="PACK_A" else "PACK_E_SHARED","pack_version":PACK_A_VERSION if arm=="PACK_A" else pack["pack_version"],"pack_fingerprint":None if arm=="PACK_A" else pack["pack_fingerprint"]}
                reject_leakage(item); item["input_fingerprint"]=fingerprint(item)
                (inputs_a if arm=="PACK_A" else inputs_e).append(item)
    return {"parent":parent_rows,"attention":attention_rows,"requests":request_rows,"packs":pack_rows,"unavailable":unavailable,"pack_a":inputs_a,"pack_e":inputs_e}


def adapt_prospective_outputs(*, episodes, attention_records, request_records, shared_pack_records, provider_models):
    """Pure interface for existing prospective v2 output shapes; never executes them."""
    return {"episodes":len(episodes),"attention_records":len(attention_records),"request_records":len(request_records),"shared_pack_records":len(shared_pack_records),"provider_models":sorted(provider_models),"external_calls":0}


def run(mode: str, output: Path = OUTPUT, attention_artifact: Path | None = None) -> dict[str, Any]:
    inv=inventory(); output.mkdir(parents=True,exist_ok=True); write_json(output/"v2_reuse_inventory.json",inv)
    if mode=="inventory": return {"mode":mode,"inventory_components":len(inv),"external_calls":0}
    state=load_frozen_package(attention_artifact=attention_artifact); episodes=rows(EPISODES); roles=rows(ROLES)
    if mode=="mock":
        result=adapt_prospective_outputs(episodes=episodes[:1],attention_records=[{"provider":"Mock","model":"mock","attention_label":"SECONDARY_DRIVER"}],request_records=[{"normalized_information_key":"mock"}],shared_pack_records=[{"pack_fingerprint":"mock"}],provider_models={"Mock":"mock"})
        write_json(output/"step5_mock.json",result); return {"mode":mode,**result}
    result=build_episode_inputs(episodes,state,roles)
    names={"parent":"episode_parent_session_map.jsonl","attention":"episode_attention_compatibility.jsonl","requests":"episode_request_compatibility.jsonl","packs":"episode_pack_compatibility.jsonl","unavailable":"compatibility_unavailable_ledger.jsonl","pack_a":"event_path_forecast_inputs_pack_a.jsonl","pack_e":"event_path_forecast_inputs_pack_e.jsonl"}
    for key,name in names.items(): write_jsonl(output/name,result[key])
    counts={"total_episodes":len(episodes),"exact_parent_session_matches":sum(row["status"]=="MATCHED" for row in result["parent"]),"attention_compatible_episodes":sum(row["status"]=="COMPATIBLE" for row in result["attention"]),"information_request_compatible_episodes":sum(row["status"]=="COMPATIBLE" for row in result["requests"]),"pack_a_compatible_episodes":sum(row["status"]=="COMPATIBLE" for row in result["packs"]),"pack_e_compatible_episodes":sum(row["status"]=="COMPATIBLE" for row in result["packs"]),"fully_step_6_ready_episodes":len({row["episode_id"] for row in result["pack_a"]})}
    unavailable=Counter(reason for row in result["unavailable"] for reason in row["reasons"])
    if counts["fully_step_6_ready_episodes"] and attention_artifact:
        decision="V2_1_FROZEN_ATTENTION_EXPORT_AND_STEP5_VALIDATED"
    elif counts["fully_step_6_ready_episodes"]:
        decision="V2_1_STEP5_V2_INFORMATION_INFRASTRUCTURE_REUSE_VALIDATED"
    else:
        decision="V2_1_STEP5_TARGETED_COMPATIBILITY_REPAIR_REQUIRED"
    manifest={"decision":decision,"mode":mode,"package":state["package"],"counts":counts,"unavailable_by_reason":dict(sorted(unavailable.items())),"pack_a_input_fingerprint":fingerprint(result["pack_a"]),"pack_e_input_fingerprint":fingerprint(result["pack_e"]),"attention_export_available":state["attention_available"],"attention_artifact":state["attention_artifact"],"external_calls":{"provider":0,"acquisition":0,"market_data":0,"apps_script":0,"google_sheets_writes":0}}
    write_json(output/"step5_manifest.json",manifest)
    report="# Step 5 v2 Information Infrastructure Reuse\n\nDecision: `{}`\n\nThe adapter reads the verified frozen v2 package and never regenerates Attention, requests, acquisition, or Packs. Historical Pack A/E inputs require exact member-level Attention lineage. The package preserves requests and Packs but lacks an Attention Map export, so affected historical Episodes remain unavailable rather than inferred from request labels.\n\n- Counts: `{}`\n- Unavailable: `{}`\n".format(manifest["decision"],counts,dict(sorted(unavailable.items())))
    (output/"step5_report.md").write_text(report)
    return manifest


def main() -> None:
    parser=argparse.ArgumentParser(); parser.add_argument("--mode",choices=("inventory","compatibility","mock"),default="compatibility"); parser.add_argument("--output",type=Path,default=OUTPUT); parser.add_argument("--attention-artifact",type=Path); args=parser.parse_args()
    print(json.dumps(run(args.mode,args.output,args.attention_artifact),sort_keys=True))


if __name__=="__main__": main()
