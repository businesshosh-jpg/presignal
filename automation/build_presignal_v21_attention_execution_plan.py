#!/usr/bin/env python3
"""Freeze the call-free Attention reconstruction execution plan for Full Round 1."""
from __future__ import annotations

import argparse
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

MATRIX_ID = "PPHB-R1-EXECUTION-MATRIX-PROVIDER-READY-20260728T171255Z-50667d4482ee"
RECONSTRUCTION_DRY_RUN_ID = "PPHB-R1-RECONSTRUCTION-DRY-RUN-20260728T134639Z-b3c9532ef93e"
OUTPUT_ROOT = ROOT / "outputs" / "presignal_v21_full_round_1_attention_execution_plan"
MATRIX_PATH = (
    ROOT
    / "outputs"
    / "presignal_v21_full_round_1_execution_matrix"
    / MATRIX_ID
    / "provider_ready_execution_matrix.jsonl"
)
EPISODE_ROWS_PATH = ROOT / "outputs" / "presignal_v21_episode_builder" / "episode_rows.jsonl"
DRY_RUN_ROOT = (
    ROOT
    / "outputs"
    / "presignal_v21_full_round_1_reconstruction_dry_run"
    / RECONSTRUCTION_DRY_RUN_ID
)
ATTENTION_PLAN_PATH = DRY_RUN_ROOT / "attention_reconstruction_plan.jsonl"
REQUEST_PLAN_PATH = DRY_RUN_ROOT / "information_request_reconstruction_plan.jsonl"
PACK_A_PLAN_PATH = DRY_RUN_ROOT / "pack_a_reconstruction_plan.jsonl"
PACK_E_PLAN_PATH = DRY_RUN_ROOT / "pack_e_reconstruction_plan.jsonl"
PROVIDER_CALL_PROJECTION_PATH = DRY_RUN_ROOT / "provider_call_projection.json"

EXPECTED_EPISODES = 462
EXPECTED_ARMS = 2772
EXPECTED_READY_ARMS = 118
EXPECTED_BLOCKED_ATTENTION_ARMS = 2478
EXPECTED_BLOCKED_ATTENTION_EPISODES = 413
EXPECTED_PROVIDER_SET = ("Anthropic", "Gemini", "OpenAI")
PROVIDER_MODELS = {
    "Anthropic": "claude-haiku-4-5",
    "Gemini": "gemini-2.5-flash-lite",
    "OpenAI": "gpt-4o-mini-2024-07-18",
}
OPEC_EPISODE_ID = "EP_EVENT_67dc98eaf62822136db2"
ATTENTION_BATCH_SIZE = 12


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def fingerprint(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def git_head() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()


def path_ref(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    os.replace(temp, path)


def write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text("".join(canonical_json(row) + "\n" for row in rows))
    os.replace(temp, path)


def load_matrix_rows() -> list[dict[str, Any]]:
    rows = read_jsonl(MATRIX_PATH)
    rows.sort(key=lambda row: (row["release_ts"], row["episode_id"], row["provider"], row["pack_arm"]))
    return rows


def load_jsonl_by_episode(path: Path) -> dict[str, dict[str, Any]]:
    rows = read_jsonl(path)
    rows.sort(key=lambda row: (row["release_ts"], row["episode_id"]))
    return {row["episode_id"]: row for row in rows}


def load_episode_rows_by_id() -> dict[str, dict[str, Any]]:
    return load_jsonl_by_episode(EPISODE_ROWS_PATH)


def blocked_attention_episodes(matrix_rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    blocked_rows = [row for row in matrix_rows if row["arm_execution_status"] == "BLOCKED_ATTENTION_RECONSTRUCTION"]
    if len(blocked_rows) != EXPECTED_BLOCKED_ATTENTION_ARMS:
        raise ValueError(f"Expected {EXPECTED_BLOCKED_ATTENTION_ARMS} blocked attention arms, found {len(blocked_rows)}")
    by_episode: dict[str, dict[str, Any]] = {}
    for row in blocked_rows:
        by_episode.setdefault(row["episode_id"], row)
    if len(by_episode) != EXPECTED_BLOCKED_ATTENTION_EPISODES:
        raise ValueError(f"Expected {EXPECTED_BLOCKED_ATTENTION_EPISODES} blocked attention episodes, found {len(by_episode)}")
    if OPEC_EPISODE_ID in by_episode:
        raise ValueError("OPEC out-of-session Episode must not enter the normal Attention plan")
    return by_episode


def ready_execution_rows(matrix_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ready = [row for row in matrix_rows if row["arm_execution_status"] == "READY_FOR_EXECUTION"]
    if len(ready) != EXPECTED_READY_ARMS:
        raise ValueError(f"Expected {EXPECTED_READY_ARMS} ready arms, found {len(ready)}")
    return ready


def provenance_category(matrix_row: Mapping[str, Any]) -> str:
    category = matrix_row["rescue_matrix_category"]
    repair = matrix_row.get("rescue_recovery_classification")
    if category == "UNCHANGED":
        return "ORIGINAL_RECONSTRUCTABLE"
    if repair == "RECOVERABLE_BY_DETERMINISTIC_LINK_REPAIR":
        return "RESCUE_DETERMINISTIC_LINK"
    if repair == "RECOVERABLE_BY_DETERMINISTIC_EVENT_DATE_LINK":
        return "RESCUE_EVENT_DATE_LINK"
    raise ValueError(f"Unsupported rescue provenance for {matrix_row['episode_id']}")


def merge_episode_session_lineage(
    blocked_by_episode: Mapping[str, Mapping[str, Any]],
    attention_plan_by_episode: Mapping[str, Mapping[str, Any]],
    episode_rows_by_id: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    for episode_id, matrix_row in blocked_by_episode.items():
        plan_row = attention_plan_by_episode.get(episode_id)
        if plan_row is None:
            raise ValueError(f"Missing attention reconstruction plan row for {episode_id}")
        episode_row = episode_rows_by_id.get(episode_id)
        if episode_row is None:
            raise ValueError(f"Missing authoritative episode row for {episode_id}")
        session_id = matrix_row.get("normal_session_id") or plan_row.get("source_session_id") or None
        if not session_id:
            raise ValueError(f"Missing merged session_id for {episode_id}")
        prompt_fingerprint = plan_row.get("prompt_fingerprint") or ""
        merged.append(
            {
                "episode_id": episode_id,
                "episode_type": "BATCH" if episode_row["same_time_cluster_flag"] else "STANDALONE",
                "release_ts": matrix_row["release_ts"],
                "release_ts_us_eastern": matrix_row.get("release_ts_us_eastern"),
                "derived_us_session_date": matrix_row.get("derived_us_session_date") or session_id.split("|")[1],
                "source_session_id": session_id,
                "attention_status": matrix_row["attention_status"],
                "pack_status": matrix_row["pack_status"],
                "current_blocker": matrix_row["arm_execution_status"],
                "rescue_matrix_category": matrix_row["rescue_matrix_category"],
                "rescue_recovery_classification": matrix_row.get("rescue_recovery_classification"),
                "provenance_category": provenance_category(matrix_row),
                "attention_reconstruction_status": plan_row["attention_reconstruction_status"],
                "attention_reason": plan_row["reason"],
                "attention_input_snapshot_status": plan_row["input_snapshot_status"],
                "attention_input_snapshot_artifacts": dict(plan_row.get("input_snapshot_artifacts") or {}),
                "required_providers": list(plan_row["required_providers"]),
                "required_models": list(plan_row["required_models"]),
                "prompt_fingerprint": prompt_fingerprint,
            }
        )
    merged.sort(key=lambda row: (row["release_ts"], row["episode_id"]))
    return merged


def call_id(session_id: str, provider: str, model: str) -> str:
    return "ATN_" + hashlib.sha256(f"{session_id}|{provider}|{model}".encode("utf-8")).hexdigest()[:20]


def build_plan(*, output_root: Path = OUTPUT_ROOT, fixed_timestamp: str | None = None) -> dict[str, Any]:
    matrix_rows = load_matrix_rows()
    if len({row["episode_id"] for row in matrix_rows}) != EXPECTED_EPISODES or len(matrix_rows) != EXPECTED_ARMS:
        raise ValueError("Unexpected governing matrix size")

    ready_rows = ready_execution_rows(matrix_rows)
    blocked_by_episode = blocked_attention_episodes(matrix_rows)
    episode_rows_by_id = load_episode_rows_by_id()
    attention_plan_by_episode = load_jsonl_by_episode(ATTENTION_PLAN_PATH)
    request_plan_by_episode = load_jsonl_by_episode(REQUEST_PLAN_PATH)
    pack_a_plan_by_episode = load_jsonl_by_episode(PACK_A_PLAN_PATH)
    pack_e_plan_by_episode = load_jsonl_by_episode(PACK_E_PLAN_PATH)
    merged = merge_episode_session_lineage(blocked_by_episode, attention_plan_by_episode, episode_rows_by_id)

    unique_sessions = sorted({row["source_session_id"] for row in merged})
    category_counts = Counter(row["provenance_category"] for row in merged)
    original_sessions = {row["source_session_id"] for row in merged if row["provenance_category"] == "ORIGINAL_RECONSTRUCTABLE"}
    rescued_sessions = {row["source_session_id"] for row in merged if row["provenance_category"] != "ORIGINAL_RECONSTRUCTABLE"}
    rescued_only_sessions = sorted(rescued_sessions - original_sessions)
    shared_sessions = sorted(rescued_sessions & original_sessions)
    original_only_sessions = sorted(original_sessions - rescued_sessions)
    rescued_episode_count_existing_sessions = sum(
        1 for row in merged if row["provenance_category"] != "ORIGINAL_RECONSTRUCTABLE" and row["source_session_id"] in shared_sessions
    )
    rescued_episode_count_new_sessions = sum(
        1 for row in merged if row["provenance_category"] != "ORIGINAL_RECONSTRUCTABLE" and row["source_session_id"] in rescued_only_sessions
    )

    episodes_by_session: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in merged:
        episodes_by_session[row["source_session_id"]].append(row)

    ready_inventory = [dict(row) for row in ready_rows]
    ready_inventory.sort(key=lambda row: (row["release_ts"], row["episode_id"], row["provider"], row["pack_arm"]))

    episode_inventory: list[dict[str, Any]] = []
    session_inventory: list[dict[str, Any]] = []
    attention_call_ledger: list[dict[str, Any]] = []
    episode_call_map: list[dict[str, Any]] = []
    pack_fanout: list[dict[str, Any]] = []

    for session_id in unique_sessions:
        session_episodes = sorted(episodes_by_session[session_id], key=lambda row: (row["release_ts"], row["episode_id"]))
        session_date = session_id.split("|")[1]
        provenance_mix = Counter(row["provenance_category"] for row in session_episodes)
        prompt_fingerprints = sorted({row["prompt_fingerprint"] for row in session_episodes if row["prompt_fingerprint"]})
        input_snapshot_artifacts = sorted(
            {
                artifact
                for row in session_episodes
                for artifact in row["attention_input_snapshot_artifacts"].values()
            }
        )
        session_inventory.append(
            {
                "source_session_id": session_id,
                "session_date": session_date,
                "episode_ids": [row["episode_id"] for row in session_episodes],
                "episode_count": len(session_episodes),
                "provenance_mix": dict(sorted(provenance_mix.items())),
                "attention_input_source": {
                    "attention_reconstruction_plan": path_ref(ATTENTION_PLAN_PATH),
                    "input_snapshot_artifacts": sorted(path_ref(Path(artifact)) for artifact in input_snapshot_artifacts),
                    "input_snapshot_statuses": sorted({row["attention_input_snapshot_status"] for row in session_episodes}),
                    "prompt_fingerprints": prompt_fingerprints,
                },
                "normalized_information_request_route": {
                    "source_plan": path_ref(REQUEST_PLAN_PATH),
                    "route": "session Attention results -> normalized Information Requests -> shared request union",
                },
                "pack_a_reconstruction_route": {
                    "source_plan": path_ref(PACK_A_PLAN_PATH),
                    "route": "deterministic Pack A rebuild from cutoff-safe historical inputs after session Attention",
                },
                "pack_e_reconstruction_route": {
                    "source_plan": path_ref(PACK_E_PLAN_PATH),
                    "route": "shared Pack E rebuild from normalized request union under the frozen shared-Pack rule",
                },
            }
        )
        for provider in EXPECTED_PROVIDER_SET:
            model = PROVIDER_MODELS[provider]
            attention_call_ledger.append(
                {
                    "call_id": call_id(session_id, provider, model),
                    "source_session_id": session_id,
                    "session_date": session_date,
                    "provider": provider,
                    "model": model,
                    "attention_input_artifact": path_ref(ATTENTION_PLAN_PATH),
                    "episode_ids": [row["episode_id"] for row in session_episodes],
                    "episode_count": len(session_episodes),
                    "input_cutoff": "per-episode frozen forecast cutoff from the governing execution matrix",
                    "output_contract_identity": "session_attention_map",
                    "execution_batch": "",
                    "execution_order": 0,
                    "retry_allowance": 1,
                    "failure_behavior": "append-only failure record; do not duplicate successful session-provider calls",
                    "call_status": "PLANNED",
                }
            )

    attention_call_ledger.sort(key=lambda row: (row["source_session_id"], row["provider"]))
    for index, row in enumerate(attention_call_ledger, start=1):
        row["execution_order"] = index

    batches = []
    batch_ids_by_call_id: dict[str, str] = {}
    for batch_index, start in enumerate(range(0, len(attention_call_ledger), ATTENTION_BATCH_SIZE), start=1):
        batch_calls = attention_call_ledger[start : start + ATTENTION_BATCH_SIZE]
        batch_id = f"ATTN_BATCH_{batch_index:03d}"
        for call in batch_calls:
            call["execution_batch"] = batch_id
            batch_ids_by_call_id[call["call_id"]] = batch_id
        batches.append(
            {
                "batch_id": batch_id,
                "execution_order_start": batch_calls[0]["execution_order"],
                "execution_order_end": batch_calls[-1]["execution_order"],
                "call_ids": [call["call_id"] for call in batch_calls],
                "provider_counts": dict(sorted(Counter(call["provider"] for call in batch_calls).items())),
                "session_count": len({call["source_session_id"] for call in batch_calls}),
                "batch_status": "PLANNED",
                "resume_rule": "resume from the next uncompleted execution_order",
            }
        )

    call_ids_by_session: dict[str, list[str]] = defaultdict(list)
    call_ids_by_session_provider: dict[str, dict[str, str]] = defaultdict(dict)
    for row in attention_call_ledger:
        call_ids_by_session[row["source_session_id"]].append(row["call_id"])
        call_ids_by_session_provider[row["source_session_id"]][row["provider"]] = row["call_id"]

    for row in merged:
        request_plan = request_plan_by_episode[row["episode_id"]]
        pack_a_plan = pack_a_plan_by_episode[row["episode_id"]]
        pack_e_plan = pack_e_plan_by_episode[row["episode_id"]]
        episode_inventory.append(
            {
                "episode_id": row["episode_id"],
                "episode_type": row["episode_type"],
                "release_ts": row["release_ts"],
                "derived_us_session_date": row["derived_us_session_date"],
                "source_session_id": row["source_session_id"],
                "provenance_category": row["provenance_category"],
                "reconstruction_route": row["attention_reconstruction_status"],
                "provider_arm_count": 6,
                "pack_arm_count": 2,
                "current_blocker": row["current_blocker"],
                "attention_input_snapshot_status": row["attention_input_snapshot_status"],
                "attention_reason": row["attention_reason"],
                "normalized_information_request_route": request_plan["information_request_reconstruction_status"],
                "pack_a_reconstruction_route": pack_a_plan["pack_a_reconstruction_status"],
                "pack_e_reconstruction_route": pack_e_plan["pack_e_reconstruction_status"],
            }
        )
        episode_call_map.append(
            {
                "episode_id": row["episode_id"],
                "source_session_id": row["source_session_id"],
                "provider_call_ids": dict(sorted(call_ids_by_session_provider[row["source_session_id"]].items())),
                "attention_call_ids": sorted(call_ids_by_session[row["source_session_id"]]),
                "call_count": len(call_ids_by_session[row["source_session_id"]]),
            }
        )
        pack_fanout.append(
            {
                "episode_id": row["episode_id"],
                "source_session_id": row["source_session_id"],
                "attention_call_ids": sorted(call_ids_by_session[row["source_session_id"]]),
                "information_request_route": request_plan["information_request_reconstruction_status"],
                "shared_request_union_rule": "approved requests from providers -> one shared Pack E -> same Pack E supplied to all forecast providers",
                "pack_a_reconstruction_status": pack_a_plan["pack_a_reconstruction_status"],
                "pack_e_reconstruction_status": pack_e_plan["pack_e_reconstruction_status"],
                "expected_forecast_arm_identities": [
                    f"{row['episode_id']}|{provider}|{pack_arm}" for provider in EXPECTED_PROVIDER_SET for pack_arm in ("PACK_A", "PACK_E")
                ],
            }
        )

    episode_inventory.sort(key=lambda row: (row["release_ts"], row["episode_id"]))
    session_inventory.sort(key=lambda row: row["source_session_id"])
    episode_call_map.sort(key=lambda row: row["episode_id"])
    pack_fanout.sort(key=lambda row: row["episode_id"])

    provider_call_projection = read_json(PROVIDER_CALL_PROJECTION_PATH)
    prior_projection_sessions = provider_call_projection["attention_calls"]["reconstructable_sessions"]
    prior_projection_calls = provider_call_projection["attention_calls"]["required"]

    calls_by_provider = Counter(row["provider"] for row in attention_call_ledger)
    calls_by_model = Counter(row["model"] for row in attention_call_ledger)
    calls_by_month = Counter(row["session_date"][:7] for row in attention_call_ledger)
    session_size_distribution = Counter(row["episode_count"] for row in session_inventory)
    largest_session = max(session_inventory, key=lambda row: (row["episode_count"], row["source_session_id"]))
    call_mix_counts = {
        "original_only": len(original_only_sessions) * len(EXPECTED_PROVIDER_SET),
        "rescued_only": len(rescued_only_sessions) * len(EXPECTED_PROVIDER_SET),
        "mixed": len(shared_sessions) * len(EXPECTED_PROVIDER_SET),
    }
    post_attention_preview = {
        "governing_matrix_id": MATRIX_ID,
        "assumption": "All planned Attention calls and deterministic Pack reconstruction succeed with no additional blocker discovered.",
        "arm_transitions": {
            "BLOCKED_ATTENTION_RECONSTRUCTION->READY_FOR_EXECUTION": EXPECTED_BLOCKED_ATTENTION_ARMS,
        },
        "status_counts_after_attention": {
            "EXISTING_IMMUTABLE_RESULT": 170,
            "READY_FOR_EXECUTION": EXPECTED_READY_ARMS + EXPECTED_BLOCKED_ATTENTION_ARMS,
            "BLOCKED_PROVIDER_CONTRACT": 0,
            "BLOCKED_ATTENTION_RECONSTRUCTION": 0,
            "BLOCKED_PACK_UNAVAILABLE": 6,
        },
        "ready_arm_total_after_attention": EXPECTED_READY_ARMS + EXPECTED_BLOCKED_ATTENTION_ARMS,
    }

    previous_plan_reconciliation = {
        "previous_unique_session_count": prior_projection_sessions,
        "previous_attention_call_count": prior_projection_calls,
        "final_unique_session_count": len(unique_sessions),
        "final_attention_call_count": len(attention_call_ledger),
        "unchanged_session_count": len(original_sessions),
        "rescue_introduced_session_count": len(rescued_only_sessions),
        "rescued_episodes_mapped_to_existing_sessions": rescued_episode_count_existing_sessions,
        "rescued_episodes_mapped_to_new_sessions": rescued_episode_count_new_sessions,
        "removed_session_count": 0,
        "rescued_only_session_ids": rescued_only_sessions,
        "reason": "The 72 rescued normal-session Episodes expand the original 62-session plan by 6 sessions and 18 session-provider Attention calls.",
    }

    ts = fixed_timestamp or now()
    seed = {
        "timestamp": ts,
        "matrix_id": MATRIX_ID,
        "dry_run_id": RECONSTRUCTION_DRY_RUN_ID,
        "ready_inventory": ready_inventory,
        "episode_inventory": episode_inventory,
        "session_inventory": session_inventory,
        "attention_call_ledger": attention_call_ledger,
        "episode_call_map": episode_call_map,
        "pack_fanout": pack_fanout,
        "post_attention_preview": post_attention_preview,
    }
    run_id = (
        "PPHB-R1-ATTENTION-EXECUTION-PLAN-"
        + ts.replace(":", "").replace("-", "")
        + "-"
        + hashlib.sha256(canonical_json(seed).encode("utf-8")).hexdigest()[:12]
    )
    run_dir = output_root / run_id
    scientific_fingerprint = fingerprint(
        {
            "ready_inventory": ready_inventory,
            "episode_inventory": episode_inventory,
            "session_inventory": session_inventory,
            "attention_call_ledger": attention_call_ledger,
            "episode_call_map": episode_call_map,
            "pack_fanout": pack_fanout,
            "post_attention_preview": post_attention_preview,
        }
    )

    run_manifest = {
        "run_id": run_id,
        "generated_at": ts,
        "git_head": git_head(),
        "provider_calls": 0,
        "attention_calls_executed": 0,
        "forecast_calls": 0,
        "research_ai_calls": 0,
        "market_data_calls": 0,
        "web_calls": 0,
        "google_writes": 0,
        "governing_matrix_id": MATRIX_ID,
        "governing_reconstruction_dry_run_id": RECONSTRUCTION_DRY_RUN_ID,
        "scientific_fingerprint": scientific_fingerprint,
    }
    governing_artifact_manifest = {
        "governing_matrix_path": path_ref(MATRIX_PATH),
        "attention_reconstruction_plan_path": path_ref(ATTENTION_PLAN_PATH),
        "authoritative_episode_rows_path": path_ref(EPISODE_ROWS_PATH),
        "information_request_reconstruction_plan_path": path_ref(REQUEST_PLAN_PATH),
        "pack_a_reconstruction_plan_path": path_ref(PACK_A_PLAN_PATH),
        "pack_e_reconstruction_plan_path": path_ref(PACK_E_PLAN_PATH),
        "provider_call_projection_path": path_ref(PROVIDER_CALL_PROJECTION_PATH),
    }
    attention_execution_contract = {
        "governing_matrix_identity": MATRIX_ID,
        "attention_input_contract": {
            "instruction_source": "automation/presignal_v21_minimal_prospective_lineage_v1.py:ATTENTION_INSTRUCTION",
            "payload_builder_source": "automation/presignal_v21_minimal_prospective_lineage_v1.py:build_prospective_attention",
            "input_snapshot_identity_source": path_ref(ATTENTION_PLAN_PATH),
        },
        "attention_output_contract": {
            "object": "session_attention_map",
            "status": "ok",
            "provider_identity_required": True,
            "session_identity_required": True,
        },
        "provider_model_routes": {
            provider: {"requested_model": PROVIDER_MODELS[provider]} for provider in EXPECTED_PROVIDER_SET
        },
        "session_deduplication_rule": "one planned Attention call per unique source_session_id x provider",
        "call_identity_rule": "ATN_<sha256(session_id|provider|model)[:20]>",
        "pack_independence_rule": "Attention is generated once per session-provider route and reused across Pack A and Pack E",
        "retry_policy": "at most one retry after a non-successful planned call; never duplicate a successful session-provider call",
        "failure_behavior": "append-only failure record and keep affected arms blocked pending replay",
        "immutability_policy": "planning artifacts are append-only and do not modify the governing execution matrix",
    }
    execution_cost_summary = {
        "total_attention_calls": len(attention_call_ledger),
        "calls_by_provider": dict(sorted(calls_by_provider.items())),
        "calls_by_model": dict(sorted(calls_by_model.items())),
        "calls_by_session_month": dict(sorted(calls_by_month.items())),
        "calls_serving_original_episodes": call_mix_counts["original_only"],
        "calls_serving_rescued_episodes": call_mix_counts["rescued_only"],
        "calls_serving_mixed_provenance": call_mix_counts["mixed"],
        "price_information": "not included; no authoritative frozen price table was used in this call-free planning Move",
    }
    attention_plan_summary = {
        "ready_arm_count_excluded": len(ready_inventory),
        "attention_blocked_arm_count": EXPECTED_BLOCKED_ATTENTION_ARMS,
        "attention_reconstruction_episode_count": len(episode_inventory),
        "original_reconstructable_episode_count": category_counts["ORIGINAL_RECONSTRUCTABLE"],
        "rescue_recovered_episode_count": category_counts["RESCUE_DETERMINISTIC_LINK"] + category_counts["RESCUE_EVENT_DATE_LINK"],
        "previous_unique_session_count": prior_projection_sessions,
        "final_unique_session_count": len(unique_sessions),
        "planned_attention_call_count": len(attention_call_ledger),
        "calls_by_provider": dict(sorted(calls_by_provider.items())),
        "calls_by_month": dict(sorted(calls_by_month.items())),
        "session_size_distribution": dict(sorted(session_size_distribution.items())),
        "largest_session": {"source_session_id": largest_session["source_session_id"], "episode_count": largest_session["episode_count"]},
        "expected_post_attention_ready_arm_total": post_attention_preview["ready_arm_total_after_attention"],
        "opec_excluded": True,
        "scientific_fingerprint": scientific_fingerprint,
    }
    attention_plan_decision = {
        "planning_status": "ATTENTION_EXECUTION_PLAN_COMPLETE",
        "session_reconciliation_decision": "SESSION_PLAN_EXPANDED_BY_RESCUE",
        "call_plan_decision": "ATTENTION_CALL_LEDGER_FROZEN",
        "main_path_decision": "MAIN_RECONSTRUCTION_PATH_READY",
        "next_step_decision": "READY_FOR_ATTENTION_EXECUTION",
        "reason": "The 72 rescued normal-session Episodes expand the prior 62-session dry-run plan to 68 sessions and 204 session-provider Attention calls while keeping the out-of-session OPEC Episode excluded.",
    }

    write_json(run_dir / "run_manifest.json", run_manifest)
    write_json(run_dir / "governing_artifact_manifest.json", governing_artifact_manifest)
    write_json(run_dir / "attention_execution_contract.json", attention_execution_contract)
    write_jsonl(run_dir / "ready_118_arm_inventory.jsonl", ready_inventory)
    write_jsonl(run_dir / "attention_blocked_413_episode_inventory.jsonl", episode_inventory)
    write_jsonl(run_dir / "unique_session_inventory.jsonl", session_inventory)
    write_json(run_dir / "previous_plan_reconciliation.json", previous_plan_reconciliation)
    write_jsonl(run_dir / "attention_call_ledger.jsonl", attention_call_ledger)
    write_json(run_dir / "attention_call_batches.json", {"batch_size": ATTENTION_BATCH_SIZE, "batches": batches})
    write_jsonl(run_dir / "episode_to_attention_call_map.jsonl", episode_call_map)
    write_jsonl(run_dir / "pack_reconstruction_fanout.jsonl", pack_fanout)
    write_json(run_dir / "post_attention_matrix_preview.json", post_attention_preview)
    write_json(run_dir / "execution_cost_summary.json", execution_cost_summary)
    write_json(run_dir / "attention_plan_summary.json", attention_plan_summary)
    write_json(run_dir / "attention_plan_decision.json", attention_plan_decision)

    return {
        "run_id": run_id,
        "run_dir": run_dir,
        "ready_inventory": ready_inventory,
        "episode_inventory": episode_inventory,
        "session_inventory": session_inventory,
        "attention_call_ledger": attention_call_ledger,
        "previous_plan_reconciliation": previous_plan_reconciliation,
        "post_attention_preview": post_attention_preview,
        "execution_cost_summary": execution_cost_summary,
        "attention_plan_summary": attention_plan_summary,
        "attention_plan_decision": attention_plan_decision,
        "scientific_fingerprint": scientific_fingerprint,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, default=OUTPUT_ROOT)
    parser.add_argument("--fixed-timestamp")
    args = parser.parse_args(argv)
    result = build_plan(output_root=args.output_root, fixed_timestamp=args.fixed_timestamp)
    print(
        json.dumps(
            {
                "run_id": result["run_id"],
                "final_unique_session_count": result["attention_plan_summary"]["final_unique_session_count"],
                "planned_attention_call_count": result["attention_plan_summary"]["planned_attention_call_count"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
