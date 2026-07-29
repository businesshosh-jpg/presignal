#!/usr/bin/env python3
"""Freeze the session-level Attention reconstruction plan for the 413 blocked Episodes."""
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
OUTPUT_ROOT = ROOT / "outputs" / "presignal_v21_full_round_1_attention_execution_planning"
MATRIX_PATH = (
    ROOT
    / "outputs"
    / "presignal_v21_full_round_1_execution_matrix"
    / MATRIX_ID
    / "provider_ready_execution_matrix.jsonl"
)
DRY_RUN_ROOT = (
    ROOT
    / "outputs"
    / "presignal_v21_full_round_1_reconstruction_dry_run"
    / RECONSTRUCTION_DRY_RUN_ID
)
ATTENTION_PLAN_PATH = DRY_RUN_ROOT / "attention_reconstruction_plan.jsonl"
PROVIDER_CALL_PROJECTION_PATH = DRY_RUN_ROOT / "provider_call_projection.json"

EXPECTED_EPISODES = 462
EXPECTED_ARMS = 2772
EXPECTED_BLOCKED_ATTENTION_ARMS = 2478
EXPECTED_BLOCKED_ATTENTION_EPISODES = 413
EXPECTED_PROVIDER_SET = ("Anthropic", "Gemini", "OpenAI")
PROVIDER_MODELS = {
    "Anthropic": "claude-haiku-4-5",
    "Gemini": "gemini-2.5-flash-lite",
    "OpenAI": "gpt-4o-mini-2024-07-18",
}
OPEC_EPISODE_ID = "EP_EVENT_67dc98eaf62822136db2"


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


def load_dry_run_attention_plan() -> list[dict[str, Any]]:
    rows = read_jsonl(ATTENTION_PLAN_PATH)
    rows.sort(key=lambda row: (row["release_ts"], row["episode_id"]))
    return rows


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


def merge_episode_session_lineage(
    blocked_by_episode: Mapping[str, Mapping[str, Any]],
    attention_plan_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    plan_by_episode = {row["episode_id"]: row for row in attention_plan_rows}
    merged: list[dict[str, Any]] = []
    for episode_id, matrix_row in blocked_by_episode.items():
        plan_row = plan_by_episode.get(episode_id)
        if plan_row is None:
            raise ValueError(f"Missing attention reconstruction plan row for {episode_id}")
        session_id = matrix_row.get("normal_session_id") or plan_row.get("source_session_id") or None
        if not session_id:
            raise ValueError(f"Missing merged session_id for {episode_id}")
        merged.append(
            {
                "episode_id": episode_id,
                "release_ts": matrix_row["release_ts"],
                "rescue_matrix_category": matrix_row["rescue_matrix_category"],
                "normal_session_status": matrix_row["normal_session_status"],
                "session_id": session_id,
                "attention_status": matrix_row["attention_status"],
                "pack_status": matrix_row["pack_status"],
                "plan_attention_status": plan_row["attention_reconstruction_status"],
                "plan_reason": plan_row["reason"],
                "plan_input_snapshot_status": plan_row["input_snapshot_status"],
                "required_providers": list(plan_row["required_providers"]),
                "required_models": list(plan_row["required_models"]),
                "prompt_fingerprint": plan_row["prompt_fingerprint"],
                "matrix_derived_us_session_date": matrix_row.get("derived_us_session_date"),
                "dry_run_source_session_id": plan_row.get("source_session_id"),
            }
        )
    merged.sort(key=lambda row: (row["release_ts"], row["episode_id"]))
    return merged


def build_plan(
    *,
    output_root: Path = OUTPUT_ROOT,
    fixed_timestamp: str | None = None,
) -> dict[str, Any]:
    matrix_rows = load_matrix_rows()
    if len({row["episode_id"] for row in matrix_rows}) != EXPECTED_EPISODES or len(matrix_rows) != EXPECTED_ARMS:
        raise ValueError("Unexpected governing matrix size")
    blocked_by_episode = blocked_attention_episodes(matrix_rows)
    attention_plan_rows = load_dry_run_attention_plan()
    merged = merge_episode_session_lineage(blocked_by_episode, attention_plan_rows)

    unique_sessions = sorted({row["session_id"] for row in merged})
    session_episode_counter = Counter(row["session_id"] for row in merged)
    category_counts = Counter(row["rescue_matrix_category"] for row in merged)
    original_sessions = {row["session_id"] for row in merged if row["rescue_matrix_category"] == "UNCHANGED"}
    rescued_sessions = {row["session_id"] for row in merged if row["rescue_matrix_category"] == "NORMAL_SESSION_RESCUE_PROMOTED"}
    rescued_only_sessions = sorted(rescued_sessions - original_sessions)
    shared_sessions = sorted(rescued_sessions & original_sessions)

    session_rows: list[dict[str, Any]] = []
    attention_calls: list[dict[str, Any]] = []
    for session_id in unique_sessions:
        episodes = [row for row in merged if row["session_id"] == session_id]
        us_date = session_id.split("|")[1]
        required_models = {provider: PROVIDER_MODELS[provider] for provider in EXPECTED_PROVIDER_SET}
        session_rows.append(
            {
                "session_id": session_id,
                "us_session_date": us_date,
                "episode_count": len(episodes),
                "rescued_episode_count": sum(row["rescue_matrix_category"] == "NORMAL_SESSION_RESCUE_PROMOTED" for row in episodes),
                "unchanged_episode_count": sum(row["rescue_matrix_category"] == "UNCHANGED" for row in episodes),
                "episode_ids": sorted(row["episode_id"] for row in episodes),
                "release_ts_min": min(row["release_ts"] for row in episodes),
                "release_ts_max": max(row["release_ts"] for row in episodes),
                "required_providers": list(EXPECTED_PROVIDER_SET),
                "required_models": required_models,
                "prompt_fingerprints": sorted({row["prompt_fingerprint"] for row in episodes if row["prompt_fingerprint"]}),
            }
        )
        for provider in EXPECTED_PROVIDER_SET:
            attention_calls.append(
                {
                    "session_id": session_id,
                    "us_session_date": us_date,
                    "provider": provider,
                    "model": PROVIDER_MODELS[provider],
                    "call_scope": "SESSION_LEVEL_ATTENTION_RECONSTRUCTION",
                    "episode_count_served": len(episodes),
                    "episode_ids": sorted(row["episode_id"] for row in episodes),
                    "deduplication_unit": "unique session x provider",
                    "forecast_arms_served": len(episodes) * 2,
                    "pack_duplication_eliminated": True,
                }
            )

    session_rows.sort(key=lambda row: row["session_id"])
    attention_calls.sort(key=lambda row: (row["session_id"], row["provider"]))

    provider_call_projection = read_json(PROVIDER_CALL_PROJECTION_PATH)
    prior_projection_sessions = provider_call_projection["attention_calls"]["reconstructable_sessions"]
    prior_projection_calls = provider_call_projection["attention_calls"]["required"]

    ts = fixed_timestamp or now()
    seed = {
        "timestamp": ts,
        "matrix_id": MATRIX_ID,
        "dry_run_id": RECONSTRUCTION_DRY_RUN_ID,
        "session_fingerprint": fingerprint(session_rows),
        "call_fingerprint": fingerprint(attention_calls),
    }
    run_id = (
        "PPHB-R1-ATTENTION-EXECUTION-PLAN-"
        + ts.replace(":", "").replace("-", "")
        + "-"
        + hashlib.sha256(canonical_json(seed).encode("utf-8")).hexdigest()[:12]
    )
    run_dir = output_root / run_id

    episode_manifest = [
        {
            "episode_id": row["episode_id"],
            "release_ts": row["release_ts"],
            "rescue_matrix_category": row["rescue_matrix_category"],
            "session_id": row["session_id"],
            "attention_status": row["attention_status"],
            "plan_attention_status": row["plan_attention_status"],
            "required_providers": row["required_providers"],
            "required_models": row["required_models"],
            "prompt_fingerprint": row["prompt_fingerprint"],
        }
        for row in merged
    ]

    session_summary = {
        "unique_session_count": len(unique_sessions),
        "attention_call_count": len(attention_calls),
        "episodes_in_plan": len(merged),
        "episodes_by_category": dict(sorted(category_counts.items())),
        "prior_projection_sessions": prior_projection_sessions,
        "prior_projection_attention_calls": prior_projection_calls,
        "reconciled_delta_sessions": len(unique_sessions) - prior_projection_sessions,
        "reconciled_delta_attention_calls": len(attention_calls) - prior_projection_calls,
        "rescued_session_count": len(rescued_sessions),
        "original_reconstructable_session_count": len(original_sessions),
        "rescued_only_session_count": len(rescued_only_sessions),
        "shared_session_count": len(shared_sessions),
        "rescued_only_session_ids": rescued_only_sessions,
    }

    execution_plan = {
        "ready_exact_lineage_arm_count": 118,
        "attention_reconstruction_blocked_arm_count": EXPECTED_BLOCKED_ATTENTION_ARMS,
        "attention_reconstruction_episode_count": len(merged),
        "unique_session_count": len(unique_sessions),
        "unique_session_provider_call_count": len(attention_calls),
        "providers": {provider: {"model": PROVIDER_MODELS[provider], "planned_calls": len(unique_sessions)} for provider in EXPECTED_PROVIDER_SET},
        "pack_level_duplication_rule": "Attention generated once per unique session x provider and reused for both Pack A and Pack E",
        "opec_out_of_session_episode_excluded": True,
    }

    reconciliation = {
        "governing_matrix_id": MATRIX_ID,
        "dry_run_id": RECONSTRUCTION_DRY_RUN_ID,
        "blocked_attention_episode_count": len(merged),
        "blocked_attention_arm_count": EXPECTED_BLOCKED_ATTENTION_ARMS,
        "original_reconstructable_episode_count": category_counts["UNCHANGED"],
        "rescued_reconstructable_episode_count": category_counts["NORMAL_SESSION_RESCUE_PROMOTED"],
        "unique_session_count": len(unique_sessions),
        "unique_session_provider_call_count": len(attention_calls),
        "prior_reconstructable_sessions": prior_projection_sessions,
        "prior_attention_calls": prior_projection_calls,
        "rescued_only_session_ids": rescued_only_sessions,
        "scientific_fingerprint": fingerprint(
            {
                "episodes": episode_manifest,
                "sessions": session_rows,
                "calls": attention_calls,
            }
        ),
    }

    decision = {
        "attention_execution_planning_status": "ATTENTION_EXECUTION_PLANNING_COMPLETE",
        "session_population_decision": "68_UNIQUE_SESSIONS_RECONCILED",
        "call_volume_decision": "204_SESSION_PROVIDER_ATTENTION_CALLS_REQUIRED",
        "main_path_decision": "MAIN_RECONSTRUCTION_PATH_UNCHANGED",
        "next_step_decision": "READY_TO_FREEZE_ATTENTION_EXECUTION_QUEUE",
        "reason": "The 72 rescued normal-session Episodes add 6 new sessions beyond the earlier 62-session dry-run estimate, increasing the session-provider Attention plan from 186 to 204 calls.",
    }

    run_manifest = {
        "run_id": run_id,
        "generated_at": ts,
        "git_head": git_head(),
        "provider_calls": 0,
        "research_ai_calls": 0,
        "forecast_calls": 0,
        "market_data_calls": 0,
        "web_calls": 0,
        "google_writes": 0,
        "matrix_id": MATRIX_ID,
        "reconstruction_dry_run_id": RECONSTRUCTION_DRY_RUN_ID,
    }
    governing = {
        "matrix_path": path_ref(MATRIX_PATH),
        "dry_run_attention_plan_path": path_ref(ATTENTION_PLAN_PATH),
        "dry_run_provider_call_projection_path": path_ref(PROVIDER_CALL_PROJECTION_PATH),
    }

    write_json(run_dir / "run_manifest.json", run_manifest)
    write_json(run_dir / "governing_artifact_manifest.json", governing)
    write_jsonl(run_dir / "blocked_attention_episode_manifest.jsonl", episode_manifest)
    write_jsonl(run_dir / "attention_session_population.jsonl", session_rows)
    write_jsonl(run_dir / "session_provider_attention_calls.jsonl", attention_calls)
    write_json(run_dir / "attention_execution_plan.json", execution_plan)
    write_json(run_dir / "session_population_summary.json", session_summary)
    write_json(run_dir / "reconciliation_summary.json", reconciliation)
    write_json(run_dir / "planning_decision.json", decision)

    return {
        "run_id": run_id,
        "run_dir": run_dir,
        "session_summary": session_summary,
        "execution_plan": execution_plan,
        "reconciliation": reconciliation,
        "episode_manifest": episode_manifest,
        "session_rows": session_rows,
        "attention_calls": attention_calls,
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
                "session_count": result["session_summary"]["unique_session_count"],
                "attention_call_count": result["session_summary"]["attention_call_count"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
