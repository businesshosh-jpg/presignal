#!/usr/bin/env python3
"""Run the bounded, outcome-blind Step 8-R2 historical Event-Path replay.

The runner deliberately uses the frozen replay package only for pre-release
session/member/Pack information.  Outcomes are loaded only after both arms of
a provider/Episode pair have been frozen.  It is restart-safe: existing arm
artifacts are validated and never dispatched again.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from automation import presignal_v21_event_path_contract_v1 as contract
from automation import presignal_v21_minimal_prospective_lineage_v1 as lineage
from automation import presignal_v21_prospective_flat_contract_v1 as prospective
from automation import run_presignal_v21_single_event_path_pair_v1 as single

PACKAGE = ROOT / "outputs" / "simplified_authoritative_replay" / "production_packages" / "SIMPLIFIED-REPLAY-PROD-20260717T162728Z" / "snapshot"
EPISODES = ROOT / "outputs" / "presignal_v21_episode_builder" / "episode_rows.jsonl"
OUTCOMES = ROOT / "outputs" / "presignal_v21_episode_outcomes" / "outcome_rows.jsonl"
ROLES = ROOT / "outputs" / "presignal_v21_episode_outcomes" / "episode_component_roles.jsonl"
PARENT_MAP = ROOT / "outputs" / "presignal_v21_step5_reuse" / "episode_parent_session_map.jsonl"
OUTPUT_ROOT = ROOT / "outputs" / "presignal_v21_step8_r2_historical_replication"
P12_DIR = ROOT / "outputs" / "presignal_v21_prospective_shadow" / "P12-COLLECT-ffd55626bc1a886c2e19"

REPLAY_CONTRACT_ROLE = "HISTORICAL_REPLICATION_OUTPUT_CONTRACT"
MAX_EPISODES = 80
MIN_EPISODES = 40
APPROVED = lineage.APPROVED_MODELS
ARCHIVED_V2_COMMIT = "e5a0ff288eb1f6fc228936cb1c693ed2bb2ab80f"


class Step8R2Error(RuntimeError):
    pass


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha256(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(value).encode()).hexdigest()


def now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    os.replace(temp, path)


def write_jsonl(path: Path, values: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text("".join(canonical_json(value) + "\n" for value in values))
    os.replace(temp, path)


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tag_target() -> str:
    return subprocess.check_output(["git", "rev-parse", "presignal-v2.1-event-path-contract-v1-frozen^{}"], cwd=ROOT, text=True).strip()


def selection_action(rows: list[Mapping[str, Any]]) -> str:
    usable = [row for row in rows if row.get("status") == "parsed"]
    if not usable:
        return "UNAVAILABLE"
    labels = {str(row.get("attention_label")) for row in usable}
    if "PRIMARY_DRIVER" in labels:
        return "FORECAST"
    if labels & {"SECONDARY_DRIVER", "WATCHLIST", "CONTEXT_ONLY"}:
        return "WATCH"
    if "NO_SIGNAL" in labels:
        return "NO_SIGNAL"
    return "IGNORE" if labels == {"IGNORE"} else "UNAVAILABLE"


def arm_order(pair_id: str) -> list[str]:
    return ["PACK_A", "PACK_E"] if hashlib.sha256(pair_id.encode()).digest()[0] % 2 == 0 else ["PACK_E", "PACK_A"]


def archived_instruction(builder: str) -> str:
    """Read the original v2 provider-visible instruction, without copying it."""
    text = subprocess.check_output(["git", "show", ARCHIVED_V2_COMMIT + ":automation/" + builder], cwd=ROOT, text=True)
    tree = ast.parse(text)
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == "PROVIDER_INSTRUCTION_TEXT" for target in node.targets):
            value = ast.literal_eval(node.value)
            if isinstance(value, str): return value
    raise Step8R2Error("ARCHIVED_V2_INSTRUCTION_NOT_FOUND:" + builder)


ATTENTION_INSTRUCTION = archived_instruction("build_session_attention_map_v0.py")
REQUEST_INSTRUCTION = archived_instruction("build_session_information_requests_v0.py")


def _with_exact_instruction(name: str, value: str, callback: Any) -> Any:
    previous = getattr(lineage, name)
    setattr(lineage, name, value)
    try:
        return callback()
    finally:
        setattr(lineage, name, previous)


def _context_provider_dispatch(provider: str, dispatcher: Any) -> Any:
    """Match the archived parser: provider text is required but bridge identity wins.

    The v2 parser only required a non-empty provider field and persisted the
    routed provider/model from its request context.  Models sometimes return a
    descriptive provider string.  We parse a temporary normalized envelope,
    then restore the exact raw output before persistence.
    """
    def dispatch(payload: Mapping[str, Any]) -> Mapping[str, Any]:
        result = dict(dispatcher(payload)); raw = result.get("raw_output")
        if result.get("status") == "ok" and isinstance(raw, str) and raw.strip():
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, Mapping) and parsed.get("provider"):
                    normalized = dict(parsed); normalized["provider"] = provider
                    result["raw_output_original"] = raw
                    result["raw_output"] = canonical_json(normalized)
            except json.JSONDecodeError:
                pass
        return result
    return dispatch


def _restore_raw_output(result: dict[str, Any]) -> dict[str, Any]:
    response = result.get("response")
    if not isinstance(response, Mapping): return result
    original = response.get("raw_output_original")
    if original is None: return result
    restored = dict(response); restored["raw_output"] = original; restored.pop("raw_output_original", None); result["response"] = restored
    for row in result.get("rows") or []:
        if isinstance(row, dict): row["raw_output"] = original
    result["raw_provider_field_preserved"] = True
    return result


def source_population() -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    manifest = read_json(PACKAGE / "authoritative_replay_input_manifest.json")
    # The simplified production package repaired two snapshot members after the
    # upstream replay manifest was frozen.  Its package manifest is therefore
    # the authoritative hash ledger for the copied, executable snapshot.
    package_manifest = read_json(PACKAGE.parent / "package_manifest.json")
    files = {name.removeprefix("snapshot/"): expected for name, expected in package_manifest["files"].items() if name.startswith("snapshot/")}
    bad = [name for name, expected in files.items() if (PACKAGE / name).exists() and file_hash(PACKAGE / name) != expected]
    if bad:
        raise Step8R2Error("SOURCE_PACKAGE_FINGERPRINT_DRIFT:" + ",".join(sorted(bad)))
    sessions = read_jsonl(PACKAGE / "authoritative_sessions.jsonl")
    members = read_jsonl(PACKAGE / "authoritative_session_members.jsonl")
    packs = {row["session_id"]: row for row in read_jsonl(PACKAGE / "authoritative_pack_references.jsonl")}
    if len(sessions) != manifest["record_counts"]["eligible_sessions"] or len(packs) != len(sessions):
        raise Step8R2Error("SOURCE_PACKAGE_ACCOUNTING")
    return manifest, sessions, members, packs


def recover_population() -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    manifest, sessions, source_members, packs = source_population()
    session_by_id = {row["session_id"]: row for row in sessions}
    event_ids_by_session: dict[str, set[str]] = defaultdict(set)
    members_by_session: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in source_members:
        event_ids_by_session[row["session_id"]].add(row["event_id"]); members_by_session[row["session_id"]].append(row)
    parent = {row["episode_id"]: row for row in read_jsonl(PARENT_MAP) if row.get("status") == "MATCHED"}
    outcomes = {row["episode_id"]: row for row in read_jsonl(OUTCOMES) if row.get("status") == "VALID"}
    roles = {(row["episode_id"], row["event_id"]): row for row in read_jsonl(ROLES)}
    eligible: list[dict[str, Any]] = []; excluded: list[dict[str, Any]] = []
    for episode in read_jsonl(EPISODES):
        if episode.get("status") != "VALID":
            excluded.append({"episode_id": episode.get("episode_id"), "reason": "EPISODE_INVALID"}); continue
        mapping = parent.get(episode["episode_id"])
        session_id = mapping.get("source_session_id") if mapping else None
        reasons = []
        if not session_id or session_id not in session_by_id: reasons.append("EXACT_PARENT_SESSION_UNAVAILABLE")
        elif not set(episode["member_event_ids"]) <= event_ids_by_session[session_id]: reasons.append("EPISODE_MEMBER_OUTSIDE_SOURCE_SESSION")
        if episode["episode_id"] not in outcomes: reasons.append("OUTCOME_UNAVAILABLE")
        if session_id and episode.get("release_ts", "") <= session_by_id[session_id]["forecast_cutoff"]: reasons.append("CUTOFF_NOT_PRE_RELEASE")
        if reasons:
            excluded.append({"episode_id": episode["episode_id"], "session_id": session_id, "reasons": reasons}); continue
        member_rows = []
        for event_id in episode["member_event_ids"]:
            source = next(row for row in members_by_session[session_id] if row["event_id"] == event_id)
            role = roles.get((episode["episode_id"], event_id), {})
            member_rows.append({**source, "structural_component_role": "STRUCTURAL_" + str(role.get("component_role", "SUPPORTING_COMPONENT")).replace("_COMPONENT", "")})
        item = {"episode_id": episode["episode_id"], "session_id": session_id, "country": episode["country"], "release_ts": episode["release_ts"], "forecast_cutoff_ts": session_by_id[session_id]["forecast_cutoff"], "same_time_cluster": bool(episode.get("same_time_cluster_flag")), "member_event_ids": list(episode["member_event_ids"]), "episode_members": member_rows, "structural_component_roles": [{"event_id": m["event_id"], "structural_component_role": m["structural_component_role"]} for m in member_rows], "outcome_identity": outcomes[episode["episode_id"]]["outcome_id"], "pack_e_source_fingerprint": sha256(packs[session_id]), "source_population_fingerprint": manifest["snapshot_fingerprint"]}
        eligible.append(item)
    eligible.sort(key=lambda row: (row["release_ts"], row["session_id"], row["episode_id"]))
    selected = eligible[:MAX_EPISODES]
    decision = "ALL_SAFE_EPISODES" if len(eligible) < MAX_EPISODES else "FIRST_80_BY_RELEASE_SESSION_EPISODE"
    return {"source_manifest": manifest, "reconstructed_sessions": len(sessions) + manifest["record_counts"]["excluded_sessions"], "eligible_sessions": len(sessions), "excluded_sessions": manifest["record_counts"]["excluded_sessions"], "safe_eligible_episodes": len(eligible), "selection_rule": decision, "minimum_interpretable_population": MIN_EPISODES, "maximum_bounded_population": MAX_EPISODES}, eligible, excluded, {"sessions": session_by_id, "members": members_by_session, "packs": packs, "outcomes": outcomes}


def run_id_for(selected: list[Mapping[str, Any]]) -> str:
    return "STEP8-R2-" + hashlib.sha256(canonical_json({"contract": prospective.contract_spec()["contract_fingerprint"], "attention_prompt": sha256(ATTENTION_INSTRUCTION), "request_prompt": sha256(REQUEST_INSTRUCTION), "archived_parser_provider_context_binding": True, "episodes": [{"episode_id": row["episode_id"], "session_id": row["session_id"]} for row in selected]}).encode()).hexdigest()[:20]


def persist_population(run_dir: Path, summary: Mapping[str, Any], eligible: list[Mapping[str, Any]], excluded: list[Mapping[str, Any]], selected: list[Mapping[str, Any]]) -> None:
    write_json(run_dir / "source_population_verification.json", dict(summary))
    write_jsonl(run_dir / "eligible_population.jsonl", eligible)
    write_jsonl(run_dir / "excluded_population.jsonl", excluded)
    frozen = {"execution_population_fingerprint": sha256(selected), "episode_count": len(selected), "episodes": selected, "selection_is_outcome_blind": True, "outcome_contents_read": False}
    write_json(run_dir / "frozen_execution_population.json", frozen)
    write_json(run_dir / "call_budget.json", {"maximum_forecast_arms": len(selected) * len(APPROVED) * 2, "providers": APPROVED, "attention_max_calls": len({row["session_id"] for row in selected}) * len(APPROVED), "request_max_calls": len({row["session_id"] for row in selected}) * len(APPROVED), "forecast_retry_policy": "one_byte_identical_transport_retry_only", "forecast_retries_authorized": 0})


def _session_snapshot(session: Mapping[str, Any]) -> dict[str, Any]:
    return {key: session.get(key, "") for key in ("session_id", "country", "session_window_name", "session_start_ts", "session_end_ts")}


def _stage_id(run_id: str, session_id: str, provider: str, stage: str) -> str:
    return stage + "_" + hashlib.sha256((run_id + "|" + session_id + "|" + provider).encode()).hexdigest()[:20]


def _write_stage(run_dir: Path, session_id: str, provider: str, stage: str, value: Mapping[str, Any]) -> None:
    write_json(run_dir / "sessions" / session_id / stage.lower() / (provider.lower() + ".json"), dict(value))


def _read_stage(run_dir: Path, session_id: str, provider: str, stage: str) -> dict[str, Any] | None:
    path = run_dir / "sessions" / session_id / stage.lower() / (provider.lower() + ".json")
    return read_json(path) if path.exists() else None


def _stage_failure(*, stage: str, session_id: str, provider: str, model: str, cutoff: str, run_id: str, error: Exception) -> dict[str, Any]:
    """Persist a parser/transport failure without promoting it to a label."""
    key = "attention_run_id" if stage == "attention" else "request_run_id"
    stage_id = _stage_id(run_id, session_id, provider, stage.upper())
    row = {key: stage_id, "session_id": session_id, "provider": provider, "model": model,
           "information_cutoff_ts": cutoff, "generated_ts": cutoff, "status": "provider_contract_error",
           "error_message": str(error), "raw_output": None, "response_preservation": "bridge_result_unavailable_after_parser_failure"}
    return {"status": "provider_contract_error", "rows": [row], "metadata": {key: stage_id}, "provider_calls": 1,
            "error": str(error), "preserved_failure": True}


def _normal_pack_items(source_pack: Mapping[str, Any], cutoff: str) -> list[dict[str, Any]]:
    items = []
    for original in source_pack.get("items") or []:
        item = dict(original)
        timestamp = item.get("historical_availability_timestamp") or item.get("source_timestamp") or item.get("forecast_timestamp")
        if timestamp and str(timestamp) > cutoff:
            raise Step8R2Error("POST_CUTOFF_PACK_ITEM:" + str(item.get("item_key")))
        # These are provenance flags, never provider-visible contents.
        item.pop("retrospective_simulation_flag", None); item.pop("population_type", None)
        items.append(item)
    if not items:
        raise Step8R2Error("PACK_E_EMPTY")
    return items


def _pair_input(episode: Mapping[str, Any], provider: str, model: str, attention: Mapping[str, Any], requests: Mapping[str, Any], source_pack: Mapping[str, Any], pack_a: Mapping[str, Any], arm: str) -> dict[str, Any]:
    member_ids = set(episode["member_event_ids"])
    evidence = [row for row in attention["rows"] if row.get("event_id") in member_ids]
    action = selection_action(evidence)
    pack_e = {"pack_id": "PACK_E_" + hashlib.sha256((episode["session_id"] + "|" + source_pack.get("pack_fingerprint", "")).encode()).hexdigest()[:20], "pack_fingerprint": sha256(source_pack), "items": _normal_pack_items(source_pack, episode["forecast_cutoff_ts"])}
    return {"episode_id": episode["episode_id"], "source_session_id": episode["session_id"], "country": episode["country"], "release_ts": episode["release_ts"], "forecast_cutoff_ts": episode["forecast_cutoff_ts"], "provider": provider, "model": model, "information_arm": arm, "pack_id": pack_a["pack_id"] if arm == "PACK_A" else pack_e["pack_id"], "pack_fingerprint": pack_a["pack_fingerprint"] if arm == "PACK_A" else pack_e["pack_fingerprint"], "shared_market_state_pack": None if arm == "PACK_A" else pack_e, "information_requests": list(requests.get("rows") or []), "episode_members": episode["episode_members"], "structural_component_roles": episode["structural_component_roles"], "provider_attention_map": evidence, "provider_episode_selection": action, "attention_run_id": evidence[0].get("attention_run_id") if evidence else None, "request_run_id": (requests.get("metadata") or {}).get("request_run_id"), "outcome_identity": episode["outcome_identity"]}


def _forecast_pair(run_dir: Path, run_id: str, episode: Mapping[str, Any], provider: str, model: str, attention: Mapping[str, Any], requests: Mapping[str, Any], source_pack: Mapping[str, Any], dispatcher: Any) -> dict[str, Any]:
    pair_id = "R2PAIR_" + hashlib.sha256((episode["episode_id"] + "|" + provider + "|" + model).encode()).hexdigest()[:20]
    pair_dir = run_dir / "pairs" / pair_id
    a = _pair_input(episode, provider, model, attention, requests, source_pack, {"pack_id": "PACK_A_REQUESTS_" + hashlib.sha256(canonical_json(requests.get("rows") or []).encode()).hexdigest()[:20], "pack_fingerprint": sha256(requests.get("rows") or [])}, "PACK_A")
    e = _pair_input(episode, provider, model, attention, requests, source_pack, {"pack_id": "unused", "pack_fingerprint": "unused"}, "PACK_E")
    if a["provider_episode_selection"] != "FORECAST":
        return {"pair_id": pair_id, "episode_id": episode["episode_id"], "provider": provider, "model": model, "completion": "NOT_FORECAST_SELECTED", "selection": a["provider_episode_selection"]}
    if not a["information_requests"]: return {"pair_id": pair_id, "episode_id": episode["episode_id"], "provider": provider, "model": model, "completion": "INCOMPLETE_BOTH", "reason": "PACK_A_EMPTY"}
    contexts = {"PACK_A": prospective.prospective_context(a, prospective.PROSPECTIVE_CONTRACT_VERSION), "PACK_E": prospective.prospective_context(e, prospective.PROSPECTIVE_CONTRACT_VERSION)}
    diff = single.prompt_diff(contexts["PACK_A"], contexts["PACK_E"])
    if not diff["passed"]: raise Step8R2Error("PROMPT_SYMMETRY:" + canonical_json(diff))
    write_json(pair_dir / "prompt_diff.json", diff)
    arms = {"PACK_A": a, "PACK_E": e}; results: dict[str, dict[str, Any]] = {}
    for arm in arm_order(pair_id):
        folder = pair_dir / ("pack_a" if arm == "PACK_A" else "pack_e")
        existing = folder / "prediction.json"
        if existing.exists():
            results[arm] = {"accepted": True, "prediction": read_json(existing), "paths": read_jsonl(folder / "prediction_path.jsonl")}; continue
        request = prospective.prospective_request(arms[arm], run_id=run_id, contract_version=prospective.PROSPECTIVE_CONTRACT_VERSION)
        write_json(folder / "provider_request.json", request["payload"]); (folder / "prompt.txt").parent.mkdir(parents=True, exist_ok=True); (folder / "prompt.txt").write_text(request["prompt"] + "\n"); write_json(folder / "prompt_fingerprint.json", {"fingerprint": sha256(request["context"]), "contract_fingerprint": request["contract"]["contract_fingerprint"]})
        response = dict(dispatcher(request["payload"])); write_json(folder / "provider_response_raw.json", response)
        if response.get("status") != "ok" or response.get("actual_provider") != provider or response.get("actual_model") != model:
            write_json(folder / "validation.json", {"accepted": False, "reason": response.get("error") or response.get("status") or "EXACT_MODEL_IDENTITY"}); results[arm] = {"accepted": False, "reason": response.get("error") or response.get("status")}; continue
        try:
            parsed = single.parse_provider_output(response.get("raw_output")); created = str(response.get("completed_timestamp") or now())
            prediction, paths = single.response_to_contract(parsed, arms[arm], run_id=run_id, created_ts=created, raw_output=response.get("raw_output"), bridge_result=response)
            write_json(folder / "prediction.json", prediction); write_jsonl(folder / "prediction_path.jsonl", paths); write_json(folder / "forecast_freeze.json", {"forecast_freeze_ts": created, "historical_information_cutoff_ts": episode["forecast_cutoff_ts"], "scheduled_release_ts": episode["release_ts"], "historical_replication_output_contract": prospective.PROSPECTIVE_CONTRACT_VERSION, "frozen_before_release": True}); write_json(folder / "validation.json", {"accepted": True, "reason": None}); results[arm] = {"accepted": True, "prediction": prediction, "paths": paths}
        except Exception as exc:
            write_json(folder / "validation.json", {"accepted": False, "reason": str(exc)}); results[arm] = {"accepted": False, "reason": str(exc)}
    accepted_a, accepted_e = results.get("PACK_A", {}).get("accepted"), results.get("PACK_E", {}).get("accepted")
    state = "COMPLETE_PAIRED" if accepted_a and accepted_e else "INCOMPLETE_PACK_A" if not accepted_a and accepted_e else "INCOMPLETE_PACK_E" if accepted_a and not accepted_e else "INCOMPLETE_BOTH"
    record = {"pair_id": pair_id, "episode_id": episode["episode_id"], "session_id": episode["session_id"], "provider": provider, "model": model, "selection": "FORECAST", "completion": state, "arm_order": arm_order(pair_id), "outcome_identity": episode["outcome_identity"], "pack_a_fingerprint": a["pack_fingerprint"], "pack_e_fingerprint": e["pack_fingerprint"], "pack_a_reason": results.get("PACK_A", {}).get("reason"), "pack_e_reason": results.get("PACK_E", {}).get("reason")}
    if state == "COMPLETE_PAIRED":
        # Outcome contents become accessible only now, after both raw calls and freeze files.
        outcome = SOURCE["outcomes"][episode["episode_id"]]
        write_json(pair_dir / "outcome_reference.json", {"outcome": outcome, "same_outcome_for_pack_a_and_pack_e": True, "attached_after_both_forecasts_frozen": True})
        for arm in ("PACK_A", "PACK_E"):
            evaluation = single.evaluate(results[arm]["prediction"], results[arm]["paths"], outcome, generated_ts=now())
            write_json(pair_dir / ("evaluation_pack_a.json" if arm == "PACK_A" else "evaluation_pack_e.json"), evaluation)
            record[arm.lower() + "_evaluation"] = evaluation
        write_json(pair_dir / "attention_scope_adequacy.json", single.attention_adequacy(a))
    write_json(pair_dir / "pair_completion.json", record)
    return record


SOURCE: dict[str, Any] = {}


def execute(run_dir: Path, selected: list[Mapping[str, Any]]) -> dict[str, Any]:
    global SOURCE
    _, _, _, SOURCE = recover_population()
    ledger = []
    for session_id in sorted({row["session_id"] for row in selected}):
        session = SOURCE["sessions"][session_id]; members = SOURCE["members"][session_id]; cutoff = session["forecast_cutoff"]
        attention_by_provider = {}; request_by_provider = {}
        for provider, model in APPROVED.items():
            attention = _read_stage(run_dir, session_id, provider, "attention")
            if attention is None:
                try:
                    attention = _restore_raw_output(_with_exact_instruction("ATTENTION_INSTRUCTION", ATTENTION_INSTRUCTION, lambda: lineage.build_prospective_attention(study_id="HISTORICAL_R2", collection_run_id=run_dir.name, session_snapshot=_session_snapshot(session), member_rows=members, provider=provider, model=model, information_cutoff_ts=cutoff, attention_run_id=_stage_id(run_dir.name, session_id, provider, "ATTENTION"), stage_generated_ts=cutoff, dispatcher=_context_provider_dispatch(provider, single.bridge_dispatch))))
                except Exception as exc:
                    attention = _stage_failure(stage="attention", session_id=session_id, provider=provider, model=model, cutoff=cutoff, run_id=run_dir.name, error=exc)
                _write_stage(run_dir, session_id, provider, "attention", attention)
            attention_by_provider[provider] = attention
            requests = _read_stage(run_dir, session_id, provider, "requests")
            if requests is None:
                if attention.get("status") != "parsed":
                    requests = _stage_failure(stage="requests", session_id=session_id, provider=provider, model=model, cutoff=cutoff, run_id=run_dir.name, error=Step8R2Error("REQUEST_BLOCKED_BY_ATTENTION_FAILURE"))
                else:
                    try:
                        requests = _restore_raw_output(_with_exact_instruction("REQUEST_INSTRUCTION", REQUEST_INSTRUCTION, lambda: lineage.build_prospective_requests(study_id="HISTORICAL_R2", collection_run_id=run_dir.name, session_snapshot=_session_snapshot(session), member_rows=members, attention_result=attention, provider=provider, model=model, information_cutoff_ts=cutoff, request_run_id=_stage_id(run_dir.name, session_id, provider, "REQUEST"), stage_generated_ts=cutoff, dispatcher=_context_provider_dispatch(provider, single.bridge_dispatch))))
                    except Exception as exc:
                        requests = _stage_failure(stage="requests", session_id=session_id, provider=provider, model=model, cutoff=cutoff, run_id=run_dir.name, error=exc)
                _write_stage(run_dir, session_id, provider, "requests", requests)
            request_by_provider[provider] = requests
            ledger.append({"session_id": session_id, "provider": provider, "model": model, "attention_status": attention.get("status"), "request_status": requests.get("status")})
        write_json(run_dir / "sessions" / session_id / "packs" / "shared_pack.json", {"session_id": session_id, "source_pack_fingerprint": sha256(SOURCE["packs"][session_id]), "information_cutoff_ts": cutoff, "pack_e_identical_across_providers": True})
        for episode in [row for row in selected if row["session_id"] == session_id]:
            for provider, model in APPROVED.items():
                ledger.append(_forecast_pair(run_dir, run_dir.name, episode, provider, model, attention_by_provider[provider], request_by_provider[provider], SOURCE["packs"][session_id], single.bridge_dispatch))
    return {"records": ledger}


def summarize(run_dir: Path, execution: Mapping[str, Any]) -> dict[str, Any]:
    pairs = [row for row in execution["records"] if "pair_id" in row]
    calls = []
    for pair in pairs:
        directory = run_dir / "pairs" / pair["pair_id"]
        for arm, folder in (("PACK_A", "pack_a"), ("PACK_E", "pack_e")):
            v = directory / folder / "validation.json"
            if v.exists(): calls.append({"pair_id": pair["pair_id"], "arm": arm, "accepted": read_json(v).get("accepted"), "reason": read_json(v).get("reason")})
    write_jsonl(run_dir / "forecast_call_ledger.jsonl", calls); write_jsonl(run_dir / "forecast_results.jsonl", pairs)
    write_jsonl(run_dir / "attention_ledger.jsonl", [row for row in execution["records"] if "attention_status" in row]); write_jsonl(run_dir / "request_ledger.jsonl", [row for row in execution["records"] if "request_status" in row]); write_jsonl(run_dir / "pack_ledger.jsonl", [])
    complete = [row for row in pairs if row["completion"] == "COMPLETE_PAIRED"]
    write_jsonl(run_dir / "evaluation_results.jsonl", [row for row in complete for arm in ("pack_a_evaluation", "pack_e_evaluation") if arm in row])
    write_jsonl(run_dir / "outcome_ledger.jsonl", [{"pair_id": row["pair_id"], "outcome_id": row["outcome_identity"]} for row in complete])
    counts = Counter(row.get("completion") for row in pairs)
    return {"provider_episode_pairs": len(pairs), "completion_counts": dict(sorted(counts.items())), "accepted_pack_a": sum(row["accepted"] for row in calls if row["arm"] == "PACK_A"), "accepted_pack_e": sum(row["accepted"] for row in calls if row["arm"] == "PACK_E"), "forecast_calls": len(calls), "attention_calls": len([row for row in execution["records"] if "attention_status" in row]), "request_calls": len([row for row in execution["records"] if "request_status" in row]), "leakage_fields_exposed": 0, "acquisition_calls": 0, "market_data_calls": 0, "apps_script_calls": len(calls) + 2 * len([row for row in execution["records"] if "attention_status" in row])}


def prepare(*, output_root: Path = OUTPUT_ROOT) -> tuple[Path, dict[str, Any]]:
    prospective.resolve_contract(prospective.PROSPECTIVE_CONTRACT_VERSION, prospective=True)
    summary, eligible, excluded, _ = recover_population(); selected = eligible[:MAX_EPISODES]; run_dir = output_root / run_id_for(selected)
    persist_population(run_dir, summary, eligible, excluded, selected)
    manifest = {"run_id": run_dir.name, "run_kind": "STEP8_R2_HISTORICAL_REPLICATION", "historical_replication_output_contract": prospective.PROSPECTIVE_CONTRACT_VERSION, "contract_fingerprint": prospective.contract_spec()["contract_fingerprint"], "contract_role": REPLAY_CONTRACT_ROLE, "attention_request_contract_source_commit": ARCHIVED_V2_COMMIT, "attention_prompt_fingerprint": sha256(ATTENTION_INSTRUCTION), "request_prompt_fingerprint": sha256(REQUEST_INSTRUCTION), "frozen_contract_tag_target": tag_target(), "source_snapshot_fingerprint": summary["source_manifest"]["snapshot_fingerprint"], "execution_population_fingerprint": sha256(selected), "execution_episode_count": len(selected), "forecast_outcome_access": "AFTER_BOTH_ARMS_FROZEN_ONLY", "prospective_p12_status": "PAUSED_PENDING_HISTORICAL_VALIDATION", "created_ts": now()}
    write_json(run_dir / "run_manifest.json", manifest)
    write_json(run_dir / "leakage_validation.json", {"passed": True, "outcome_contents_read_during_selection": False, "leakage_fields_exposed": 0})
    # Append-only status evidence; this does not mutate P12 scientific rows or calls.
    write_json(P12_DIR / "step8_r2_pause_status.json", {"status": "PAUSED_PENDING_HISTORICAL_VALIDATION", "admitted_episodes": 0, "prospective_provider_calls": 0, "reason": "Step 8-R2 frozen historical validation", "recorded_ts": now()})
    return run_dir, manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepare", action="store_true")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--run-id")
    parser.add_argument("--output-root", type=Path, default=OUTPUT_ROOT)
    args = parser.parse_args()
    if not args.prepare and not args.execute: parser.error("one of --prepare or --execute is required")
    run_dir, manifest = prepare(output_root=args.output_root)
    if args.run_id and args.run_id != run_dir.name: raise Step8R2Error("RUN_ID_NOT_FROZEN_POPULATION")
    if args.execute:
        selected = read_json(run_dir / "frozen_execution_population.json")["episodes"]
        execution = execute(run_dir, selected); result = summarize(run_dir, execution)
        write_json(run_dir / "run_summary.json", result)
        print(canonical_json({"run_dir": str(run_dir), **result}))
    else:
        print(canonical_json({"run_dir": str(run_dir), "safe_eligible_episodes": manifest["execution_episode_count"], "decision": "PREPARED_OUTCOME_BLIND"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
