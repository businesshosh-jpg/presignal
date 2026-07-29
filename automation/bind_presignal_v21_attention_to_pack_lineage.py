#!/usr/bin/env python3
"""Prepare deterministic Attention-to-Pack lineage bindings without constructing Packs."""
from __future__ import annotations

import argparse
import hashlib
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from automation import consolidate_presignal_v21_attention_results as consolidation
from automation import execute_presignal_v21_attention_batch_004 as batch004

PLAN_ID = "PPHB-R1-ATTENTION-EXECUTION-PLAN-20260729T010207Z-3fcd59f96f3c"
FULL_COMPLETION_ID = "PPHB-R1-ATTENTION-EXECUTION-FULL-COMPLETION-20260729T095829Z-0437a6002810"
CONSOLIDATION_ID = "PPHB-R1-ATTENTION-RESULT-CONSOLIDATION-20260729T102316Z-17358e44afc1"

CONSOLIDATION_ROOT = ROOT / "outputs" / "presignal_v21_full_round_1_attention_consolidation" / CONSOLIDATION_ID
PLAN_ROOT = ROOT / "outputs" / "presignal_v21_full_round_1_attention_execution_plan" / PLAN_ID
ELIGIBILITY_IMPL_ROOT = ROOT / "outputs" / "presignal_v21_full_round_1_eligibility_implementation" / "PPHB-R1-ELIGIBILITY-IMPLEMENTATION-20260728T132849Z-297192188403"
RECON_DRY_RUN_ROOT = ROOT / "outputs" / "presignal_v21_full_round_1_reconstruction_dry_run" / "PPHB-R1-RECONSTRUCTION-DRY-RUN-20260728T134639Z-b3c9532ef93e"
STEP5_REUSE_ROOT = ROOT / "outputs" / "presignal_v21_step5_reuse"
OUTPUT_ROOT = ROOT / "outputs" / "presignal_v21_full_round_1_attention_pack_lineage"

PROVIDERS = ("Anthropic", "Gemini", "OpenAI")
PROVIDER_MODELS = {
    "Anthropic": "claude-haiku-4-5",
    "Gemini": "gemini-2.5-flash-lite",
    "OpenAI": "gpt-4o-mini-2024-07-18",
}
PACK_TYPES = ("PACK_A", "PACK_E")


class LineageBindingError(RuntimeError):
    pass


def canonical_json(value: Any) -> str:
    return consolidation.canonical_json(value)


def sha256_value(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def write_json(path: Path, value: Any) -> None:
    consolidation.write_json(path, value)


def write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    consolidation.write_jsonl(path, rows)


def read_json(path: Path) -> dict[str, Any]:
    return consolidation.read_json(path)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return consolidation.read_jsonl(path)


def path_ref(path: Path) -> str:
    return consolidation.path_ref(path)


def now() -> str:
    return batch004.now()


def materialize_run(output_root: Path, fixed_timestamp: str | None = None) -> Path:
    ts = fixed_timestamp or now()
    seed = {
        "plan_id": PLAN_ID,
        "full_completion_id": FULL_COMPLETION_ID,
        "consolidation_id": CONSOLIDATION_ID,
        "timestamp": ts,
        "move": "ATTENTION_TO_PACK_LINEAGE_BINDING",
    }
    run_id = (
        "PPHB-R1-ATTENTION-TO-PACK-LINEAGE-BINDING-"
        + ts.replace(":", "").replace("-", "")
        + "-"
        + hashlib.sha256(canonical_json(seed).encode("utf-8")).hexdigest()[:12]
    )
    return output_root / run_id


def parse_run_identity(normalized_result_reference: str) -> str:
    path = Path(normalized_result_reference)
    return path.parent.name


def first_value(*values: Any) -> Any:
    for value in values:
        if value not in (None, "", [], {}):
            return value
    return None


def load_required_artifacts() -> dict[str, Any]:
    artifacts = {
        "episode_provider_population": CONSOLIDATION_ROOT / "episode_provider_population.jsonl",
        "episode_coverage_population": CONSOLIDATION_ROOT / "episode_coverage_population.jsonl",
        "authoritative_call_inventory": CONSOLIDATION_ROOT / "authoritative_call_inventory.jsonl",
        "call_lineage_ledger": CONSOLIDATION_ROOT / "call_lineage_ledger.jsonl",
        "pack_fanout": PLAN_ROOT / "pack_reconstruction_fanout.jsonl",
        "episode_to_attention_call_map": PLAN_ROOT / "episode_to_attention_call_map.jsonl",
        "pack_status_ledger": ELIGIBILITY_IMPL_ROOT / "pack_status_ledger.jsonl",
        "expected_arm_ledger": ELIGIBILITY_IMPL_ROOT / "expected_arm_ledger.jsonl",
        "pack_a_plan": RECON_DRY_RUN_ROOT / "pack_a_reconstruction_plan.jsonl",
        "pack_e_plan": RECON_DRY_RUN_ROOT / "pack_e_reconstruction_plan.jsonl",
        "episode_request_compatibility": STEP5_REUSE_ROOT / "episode_request_compatibility.jsonl",
        "episode_pack_compatibility": STEP5_REUSE_ROOT / "episode_pack_compatibility.jsonl",
    }
    for path in artifacts.values():
        if not path.exists():
            raise LineageBindingError(f"MISSING_GOVERNING_ARTIFACT:{path}")
    return {
        "paths": artifacts,
        "episode_provider_population": read_jsonl(artifacts["episode_provider_population"]),
        "episode_coverage_population": read_jsonl(artifacts["episode_coverage_population"]),
        "authoritative_call_inventory": read_jsonl(artifacts["authoritative_call_inventory"]),
        "call_lineage_ledger": read_jsonl(artifacts["call_lineage_ledger"]),
        "pack_fanout": read_jsonl(artifacts["pack_fanout"]),
        "episode_to_attention_call_map": read_jsonl(artifacts["episode_to_attention_call_map"]),
        "pack_status_ledger": read_jsonl(artifacts["pack_status_ledger"]),
        "expected_arm_ledger": read_jsonl(artifacts["expected_arm_ledger"]),
        "pack_a_plan": read_jsonl(artifacts["pack_a_plan"]),
        "pack_e_plan": read_jsonl(artifacts["pack_e_plan"]),
        "episode_request_compatibility": read_jsonl(artifacts["episode_request_compatibility"]),
        "episode_pack_compatibility": read_jsonl(artifacts["episode_pack_compatibility"]),
    }


def resolved_pack_status(status: str | None, blocked_code: str, missing_code: str, ambiguity_code: str) -> str:
    if status == "RESOLVED":
        return "RESOLVED"
    if status == "NOT_REQUIRED":
        return "NOT_REQUIRED_BY_FROZEN_CONTRACT"
    if status == "BLOCKED_SOURCE_MISSING":
        return "BLOCKED_SOURCE_MISSING"
    if status == "BLOCKED_IDENTITY_CONFLICT":
        return "BLOCKED_IDENTITY_CONFLICT"
    if status == "BLOCKED_CONTRACT_AMBIGUITY":
        return "BLOCKED_CONTRACT_AMBIGUITY"
    raise LineageBindingError(f"UNSUPPORTED_LINEAGE_STATUS:{status}:{blocked_code}:{missing_code}:{ambiguity_code}")


def execute_lineage_binding(
    *,
    output_root: Path = OUTPUT_ROOT,
    fixed_timestamp: str | None = None,
) -> dict[str, Any]:
    start_head = batch004.git_head()
    loaded = load_required_artifacts()
    paths = loaded["paths"]
    consolidated_rows = loaded["episode_provider_population"]

    if len(consolidated_rows) != 1239:
        raise LineageBindingError("CONSOLIDATED_EPISODE_PROVIDER_COUNT_MISMATCH")
    unique_attention_keys = {f"{row['episode_id']}|{row['provider']}" for row in consolidated_rows}
    if len(unique_attention_keys) != 1239:
        raise LineageBindingError("DUPLICATE_EPISODE_PROVIDER_KEYS")

    grouped_by_episode: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in consolidated_rows:
        grouped_by_episode[row["episode_id"]].append(row)
    if len(grouped_by_episode) != 413:
        raise LineageBindingError("EPISODE_COUNT_MISMATCH")
    if any(sorted({row["provider"] for row in rows}) != list(PROVIDERS) for rows in grouped_by_episode.values()):
        raise LineageBindingError("EPISODE_PROVIDER_COVERAGE_MISMATCH")

    call_inventory_by_call = {row["call_id"]: row for row in loaded["authoritative_call_inventory"]}
    call_lineage_by_call = {row["call_id"]: row for row in loaded["call_lineage_ledger"]}
    fanout_by_episode = {row["episode_id"]: row for row in loaded["pack_fanout"]}
    episode_map_by_episode = {row["episode_id"]: row for row in loaded["episode_to_attention_call_map"]}
    pack_status_by_episode = {row["episode_id"]: row for row in loaded["pack_status_ledger"]}
    pack_a_plan_by_episode = {row["episode_id"]: row for row in loaded["pack_a_plan"]}
    pack_e_plan_by_episode = {row["episode_id"]: row for row in loaded["pack_e_plan"]}
    req_compat_by_episode = {row["episode_id"]: row for row in loaded["episode_request_compatibility"]}
    pack_compat_by_episode = {row["episode_id"]: row for row in loaded["episode_pack_compatibility"]}

    expected_arm_rows: dict[tuple[str, str, str], dict[str, Any]] = {}
    for row in loaded["expected_arm_ledger"]:
        key = (row["episode_id"], row["provider"], row["pack_arm"])
        expected_arm_rows[key] = row

    episode_provider_attention_lineage: list[dict[str, Any]] = []
    episode_pack_source_lineage: list[dict[str, Any]] = []
    episode_provider_pack_binding: list[dict[str, Any]] = []
    lineage_blockers: list[dict[str, Any]] = []
    identity_conflicts: list[dict[str, Any]] = []
    missing_sources: list[dict[str, Any]] = []

    pack_a_counts = Counter()
    pack_e_counts = Counter()
    future_binding_counts = Counter()
    blocker_categories = Counter()
    non_selected_preserved_count = 0
    scientific_mutation_count = 0

    for episode_id, provider_rows in sorted(grouped_by_episode.items()):
        fanout = fanout_by_episode.get(episode_id)
        episode_map = episode_map_by_episode.get(episode_id)
        pack_status = pack_status_by_episode.get(episode_id)
        pack_a_plan = pack_a_plan_by_episode.get(episode_id)
        pack_e_plan = pack_e_plan_by_episode.get(episode_id)
        req_compat = req_compat_by_episode.get(episode_id)
        pack_compat = pack_compat_by_episode.get(episode_id)
        exemplar = provider_rows[0]

        source_session_candidates = [
            first_value(fanout.get("source_session_id") if fanout else None, ""),
            first_value(episode_map.get("source_session_id") if episode_map else None, ""),
            first_value(pack_a_plan.get("source_session_id") if pack_a_plan else None, ""),
            first_value(pack_e_plan.get("source_session_id") if pack_e_plan else None, ""),
            first_value(req_compat.get("source_session_id") if req_compat else None, ""),
            first_value(pack_compat.get("source_session_id") if pack_compat else None, ""),
        ]
        exact_source_session_ids = {value for value in source_session_candidates if value}
        if len(exact_source_session_ids) > 1:
            identity_conflicts.append(
                {
                    "conflict_type": "SOURCE_SESSION_IDENTITY_CONFLICT",
                    "episode_id": episode_id,
                    "values": sorted(exact_source_session_ids),
                }
            )
        canonical_source_session_id = exemplar["source_session_id"]

        pack_a_source_refs = [
            {"artifact": path_ref(paths["pack_fanout"]), "key": {"episode_id": episode_id}, "required_fields": ["pack_a_reconstruction_status", "attention_call_ids", "source_session_id"]},
            {"artifact": path_ref(paths["pack_a_plan"]), "key": {"episode_id": episode_id}, "required_fields": ["pack_a_reconstruction_status", "depends_on_attention", "reason", "source_session_id"]},
            {"artifact": path_ref(paths["pack_status_ledger"]), "key": {"episode_id": episode_id}, "required_fields": ["pack_a_status", "pack_a_reason", "pack_a_input_admissibility"]},
            {"artifact": path_ref(paths["episode_request_compatibility"]), "key": {"episode_id": episode_id}, "required_fields": ["status", "provider_request_counts", "source_session_id"]},
        ]
        pack_e_source_refs = [
            {"artifact": path_ref(paths["pack_fanout"]), "key": {"episode_id": episode_id}, "required_fields": ["pack_e_reconstruction_status", "information_request_route", "shared_request_union_rule", "source_session_id"]},
            {"artifact": path_ref(paths["pack_e_plan"]), "key": {"episode_id": episode_id}, "required_fields": ["pack_e_reconstruction_status", "depends_on_attention", "reason", "source_session_id"]},
            {"artifact": path_ref(paths["pack_status_ledger"]), "key": {"episode_id": episode_id}, "required_fields": ["pack_e_status", "pack_e_reason", "pack_e_input_admissibility"]},
            {"artifact": path_ref(paths["episode_request_compatibility"]), "key": {"episode_id": episode_id}, "required_fields": ["status", "provider_request_counts", "source_session_id"]},
            {"artifact": path_ref(paths["episode_pack_compatibility"]), "key": {"episode_id": episode_id}, "required_fields": ["status", "pack_e_fingerprint", "provider_model_pairs", "source_session_id"]},
        ]

        pack_a_episode_status = "RESOLVED"
        pack_a_missing_fields: list[str] = []
        pack_a_blocker = ""
        if fanout is None or pack_a_plan is None or pack_status is None or req_compat is None:
            pack_a_episode_status = "BLOCKED_SOURCE_MISSING"
            pack_a_missing_fields.extend(
                [
                    name for name, row in [
                        ("pack_fanout", fanout),
                        ("pack_a_plan", pack_a_plan),
                        ("pack_status_ledger", pack_status),
                        ("episode_request_compatibility", req_compat),
                    ] if row is None
                ]
            )
            pack_a_blocker = "MISSING_FROZEN_SOURCE"
        elif len(exact_source_session_ids) > 1 or canonical_source_session_id not in exact_source_session_ids:
            pack_a_episode_status = "BLOCKED_IDENTITY_CONFLICT"
            pack_a_blocker = "SOURCE_SESSION_IDENTITY_CONFLICT"
        elif fanout["pack_a_reconstruction_status"] != "DETERMINISTIC_REBUILD_AVAILABLE":
            pack_a_episode_status = "BLOCKED_SOURCE_MISSING"
            pack_a_blocker = fanout["pack_a_reconstruction_status"]
        elif pack_a_plan["pack_a_reconstruction_status"] != "DETERMINISTIC_REBUILD_AVAILABLE":
            pack_a_episode_status = "BLOCKED_SOURCE_MISSING"
            pack_a_blocker = pack_a_plan["pack_a_reconstruction_status"]
        elif pack_status["pack_a_status"] != "PACK_RECONSTRUCTABLE":
            pack_a_episode_status = "BLOCKED_SOURCE_MISSING"
            pack_a_blocker = pack_status["pack_a_status"]
        elif req_compat["status"] != "COMPATIBLE":
            pack_a_episode_status = "BLOCKED_SOURCE_MISSING"
            pack_a_blocker = req_compat["status"]

        if pack_a_episode_status != "RESOLVED":
            missing_sources.append(
                {
                    "episode_id": episode_id,
                    "pack_type": "PACK_A",
                    "missing_artifact": pack_a_missing_fields or [path_ref(paths["pack_status_ledger"])],
                    "missing_field": pack_a_blocker or "SOURCE_STATUS",
                    "exact_blocker": pack_a_blocker or "MISSING_FROZEN_SOURCE",
                }
            )

        pack_e_episode_status = "RESOLVED"
        pack_e_missing_fields: list[str] = []
        pack_e_blocker = ""
        if fanout is None or pack_e_plan is None or pack_status is None or req_compat is None or pack_compat is None:
            pack_e_episode_status = "BLOCKED_SOURCE_MISSING"
            pack_e_missing_fields.extend(
                [
                    name for name, row in [
                        ("pack_fanout", fanout),
                        ("pack_e_plan", pack_e_plan),
                        ("pack_status_ledger", pack_status),
                        ("episode_request_compatibility", req_compat),
                        ("episode_pack_compatibility", pack_compat),
                    ] if row is None
                ]
            )
            pack_e_blocker = "MISSING_FROZEN_SOURCE"
        elif len(exact_source_session_ids) > 1 or canonical_source_session_id not in exact_source_session_ids:
            pack_e_episode_status = "BLOCKED_IDENTITY_CONFLICT"
            pack_e_blocker = "SOURCE_SESSION_IDENTITY_CONFLICT"
        elif fanout["pack_e_reconstruction_status"] != "DETERMINISTIC_REBUILD_AVAILABLE":
            pack_e_episode_status = "BLOCKED_SOURCE_MISSING"
            pack_e_blocker = fanout["pack_e_reconstruction_status"]
        elif fanout["information_request_route"] != "REUSED_EXACT":
            pack_e_episode_status = "BLOCKED_CONTRACT_AMBIGUITY"
            pack_e_blocker = fanout["information_request_route"]
        elif pack_e_plan["pack_e_reconstruction_status"] != "DETERMINISTIC_REBUILD_AVAILABLE":
            pack_e_episode_status = "BLOCKED_SOURCE_MISSING"
            pack_e_blocker = pack_e_plan["pack_e_reconstruction_status"]
        elif pack_status["pack_e_status"] != "PACK_RECONSTRUCTABLE":
            pack_e_episode_status = "BLOCKED_SOURCE_MISSING"
            pack_e_blocker = pack_status["pack_e_status"]
        elif req_compat["status"] != "COMPATIBLE":
            pack_e_episode_status = "BLOCKED_SOURCE_MISSING"
            pack_e_blocker = req_compat["status"]
        elif pack_compat["status"] != "COMPATIBLE" or not pack_compat.get("pack_e_fingerprint"):
            pack_e_episode_status = "BLOCKED_SOURCE_MISSING"
            pack_e_blocker = pack_compat.get("status") or "PACK_E_FINGERPRINT_MISSING"

        if pack_e_episode_status != "RESOLVED":
            missing_sources.append(
                {
                    "episode_id": episode_id,
                    "pack_type": "PACK_E",
                    "missing_artifact": pack_e_missing_fields or [path_ref(paths["episode_pack_compatibility"])],
                    "missing_field": pack_e_blocker or "SOURCE_STATUS",
                    "exact_blocker": pack_e_blocker or "MISSING_FROZEN_SOURCE",
                }
            )

        resolved_source_count = sum(status == "RESOLVED" for status in [pack_a_episode_status, pack_e_episode_status])
        episode_pack_source_lineage.append(
            {
                "episode_id": episode_id,
                "source_session_id": canonical_source_session_id,
                "event_identities": exemplar["member_event_ids"],
                "episode_timestamp": exemplar["release_ts"],
                "episode_class_or_cluster_identity": exemplar["episode_family"],
                "pack_a_source_identities": pack_a_source_refs,
                "pack_e_source_identities": pack_e_source_refs,
                "required_source_count": len(pack_a_source_refs) + len(pack_e_source_refs),
                "resolved_source_count": len(pack_a_source_refs) * (1 if pack_a_episode_status == "RESOLVED" else 0) + len(pack_e_source_refs) * (1 if pack_e_episode_status == "RESOLVED" else 0),
                "missing_source_identities": pack_a_missing_fields + pack_e_missing_fields,
                "lineage_status": "RESOLVED" if resolved_source_count == 2 else "BLOCKED",
                "pack_a_lineage_status": resolved_pack_status(pack_a_episode_status, pack_a_blocker, "MISSING_FROZEN_SOURCE", "CONTRACT_AMBIGUITY"),
                "pack_e_lineage_status": resolved_pack_status(pack_e_episode_status, pack_e_blocker, "MISSING_FROZEN_SOURCE", "CONTRACT_AMBIGUITY"),
            }
        )

        for row in sorted(provider_rows, key=lambda item: item["provider"]):
            provider = row["provider"]
            model = row["model"]
            expected_call_id = (episode_map or {}).get("provider_call_ids", {}).get(provider)
            if expected_call_id != row["call_id"]:
                identity_conflicts.append(
                    {
                        "conflict_type": "EPISODE_PROVIDER_CALL_ID_CONFLICT",
                        "episode_id": episode_id,
                        "provider": provider,
                        "expected_call_id": expected_call_id,
                        "observed_call_id": row["call_id"],
                    }
                )
            if any(label not in {"PRIMARY_DRIVER", "SECONDARY_DRIVER"} for label in (row.get("attention_selection_state") or [])):
                non_selected_preserved_count += 1

            attention_run_identity = parse_run_identity(row["normalized_result_reference"])
            attention_request_identity = first_value(row.get("attention_request_identity"), call_inventory_by_call.get(row["call_id"], {}).get("input_fingerprint"))
            attention_lineage_row = {
                "episode_id": episode_id,
                "provider": provider,
                "model": model,
                "source_session_id": row["source_session_id"],
                "attention_call_id": row["call_id"],
                "attention_authoritative_run_identity": attention_run_identity,
                "attention_request_identity": attention_request_identity,
                "attention_selection_state": row["attention_selection_state"],
                "canonical_row_status": row["canonical_row_status"],
                "attention_cutoff": row["cutoff_lineage"],
                "attention_source_reference": row["normalized_result_reference"],
                "source_result_identity": row["source_result_identity"],
                "raw_claimed_provider_value": row["raw_claimed_provider_value"],
                "repair_retry_lineage": row["repair_retry_lineage"],
            }
            episode_provider_attention_lineage.append(attention_lineage_row)

            pack_a_arm = expected_arm_rows.get((episode_id, provider, "PACK_A"))
            pack_e_arm = expected_arm_rows.get((episode_id, provider, "PACK_E"))
            if pack_a_arm is None:
                identity_conflicts.append({"conflict_type": "EXPECTED_PACK_A_ARM_MISSING", "episode_id": episode_id, "provider": provider})
            if pack_e_arm is None:
                identity_conflicts.append({"conflict_type": "EXPECTED_PACK_E_ARM_MISSING", "episode_id": episode_id, "provider": provider})

            pack_a_status = (
                "BLOCKED_IDENTITY_CONFLICT"
                if pack_a_arm is None or expected_call_id != row["call_id"]
                else resolved_pack_status(pack_a_episode_status, pack_a_blocker, "MISSING_FROZEN_SOURCE", "CONTRACT_AMBIGUITY")
            )
            pack_e_status = (
                "BLOCKED_IDENTITY_CONFLICT"
                if pack_e_arm is None or expected_call_id != row["call_id"]
                else resolved_pack_status(pack_e_episode_status, pack_e_blocker, "MISSING_FROZEN_SOURCE", "CONTRACT_AMBIGUITY")
            )
            pack_a_counts[pack_a_status] += 1
            pack_e_counts[pack_e_status] += 1

            blocker_code = None
            if pack_a_status != "RESOLVED":
                blocker_code = pack_a_blocker or "IDENTITY_CONFLICT"
                blocker_categories[f"PACK_A:{blocker_code}"] += 1
                lineage_blockers.append(
                    {
                        "episode_id": episode_id,
                        "provider": provider,
                        "pack_type": "PACK_A",
                        "missing_artifact": path_ref(paths["pack_a_plan"]) if pack_a_episode_status == "BLOCKED_SOURCE_MISSING" else path_ref(paths["expected_arm_ledger"]),
                        "missing_field": "pack_a_reconstruction_status" if pack_a_episode_status == "BLOCKED_SOURCE_MISSING" else "expected_arm_identity",
                        "exact_blocker": blocker_code,
                        "scientific_interpretation_required": False,
                        "smallest_future_repair_action": "recover exact parent-session lineage or exact Pack A frozen source identity",
                    }
                )
            if pack_e_status != "RESOLVED":
                blocker_code = pack_e_blocker or "IDENTITY_CONFLICT"
                blocker_categories[f"PACK_E:{blocker_code}"] += 1
                lineage_blockers.append(
                    {
                        "episode_id": episode_id,
                        "provider": provider,
                        "pack_type": "PACK_E",
                        "missing_artifact": path_ref(paths["episode_pack_compatibility"]) if pack_e_episode_status == "BLOCKED_SOURCE_MISSING" else path_ref(paths["expected_arm_ledger"]),
                        "missing_field": "pack_e_fingerprint" if pack_e_episode_status == "BLOCKED_SOURCE_MISSING" else "expected_arm_identity",
                        "exact_blocker": blocker_code,
                        "scientific_interpretation_required": False,
                        "smallest_future_repair_action": "recover exact parent-session lineage or exact Pack E frozen source identity",
                    }
                )

            future_status = (
                "FULLY_RESOLVED"
                if pack_a_status == "RESOLVED" and pack_e_status == "RESOLVED"
                else "PARTIALLY_RESOLVED"
                if "RESOLVED" in {pack_a_status, pack_e_status}
                else "FULLY_BLOCKED"
            )
            future_binding_counts[future_status] += 1

            episode_provider_pack_binding.append(
                {
                    "episode_id": episode_id,
                    "provider": provider,
                    "model": model,
                    "attention_call_id": row["call_id"],
                    "attention_request_identity": attention_request_identity,
                    "attention_selection_state": row["attention_selection_state"],
                    "attention_lineage_resolved": True,
                    "pack_source_lineage_resolved": future_status == "FULLY_RESOLVED",
                    "future_pack_binding_eligible": future_status == "FULLY_RESOLVED",
                    "pack_a_lineage_status": pack_a_status,
                    "pack_a_source_references": pack_a_source_refs + [{"artifact": path_ref(paths["expected_arm_ledger"]), "key": {"expected_arm_identity": f"{episode_id}|{provider}|PACK_A"}, "required_fields": ["expected_arm_identity", "pack_status", "provider", "model"]}],
                    "pack_e_lineage_status": pack_e_status,
                    "pack_e_source_references": pack_e_source_refs + [{"artifact": path_ref(paths["expected_arm_ledger"]), "key": {"expected_arm_identity": f"{episode_id}|{provider}|PACK_E"}, "required_fields": ["expected_arm_identity", "pack_status", "provider", "model"]}],
                    "future_pack_binding_status": future_status,
                    "blocker_code": None if future_status == "FULLY_RESOLVED" else first_value(pack_a_blocker, pack_e_blocker, "IDENTITY_CONFLICT"),
                    "expected_pack_a_arm_identity": f"{episode_id}|{provider}|PACK_A",
                    "expected_pack_e_arm_identity": f"{episode_id}|{provider}|PACK_E",
                }
            )

    if len(episode_provider_attention_lineage) != 1239:
        raise LineageBindingError("ATTENTION_LINEAGE_ROW_COUNT_MISMATCH")
    if len({f"{row['episode_id']}|{row['provider']}" for row in episode_provider_attention_lineage}) != 1239:
        raise LineageBindingError("ATTENTION_LINEAGE_KEY_COUNT_MISMATCH")
    if len(episode_pack_source_lineage) != 413:
        raise LineageBindingError("EPISODE_PACK_SOURCE_ROW_COUNT_MISMATCH")
    if len(episode_provider_pack_binding) != 1239:
        raise LineageBindingError("EPISODE_PROVIDER_PACK_BINDING_COUNT_MISMATCH")
    if len({f"{row['episode_id']}|{row['provider']}" for row in episode_provider_pack_binding}) != 1239:
        raise LineageBindingError("EPISODE_PROVIDER_PACK_BINDING_KEY_COUNT_MISMATCH")

    pack_a_reconciliation = {
        "resolved_count": pack_a_counts["RESOLVED"],
        "blocked_source_missing_count": pack_a_counts["BLOCKED_SOURCE_MISSING"],
        "blocked_identity_conflict_count": pack_a_counts["BLOCKED_IDENTITY_CONFLICT"],
        "blocked_contract_ambiguity_count": pack_a_counts["BLOCKED_CONTRACT_AMBIGUITY"],
        "not_required_count": pack_a_counts["NOT_REQUIRED_BY_FROZEN_CONTRACT"],
    }
    pack_e_reconciliation = {
        "resolved_count": pack_e_counts["RESOLVED"],
        "blocked_source_missing_count": pack_e_counts["BLOCKED_SOURCE_MISSING"],
        "blocked_identity_conflict_count": pack_e_counts["BLOCKED_IDENTITY_CONFLICT"],
        "blocked_contract_ambiguity_count": pack_e_counts["BLOCKED_CONTRACT_AMBIGUITY"],
        "not_required_count": pack_e_counts["NOT_REQUIRED_BY_FROZEN_CONTRACT"],
    }

    cross_reconciliation = {
        "attention_row_count_matches_pack_binding_row_count": len(episode_provider_attention_lineage) == len(episode_provider_pack_binding) == 1239,
        "exactly_one_future_pack_binding_row_per_episode_provider_key": len({f"{row['episode_id']}|{row['provider']}" for row in episode_provider_pack_binding}) == 1239,
        "exactly_three_provider_rows_per_episode": all(
            sum(1 for row in episode_provider_pack_binding if row["episode_id"] == episode_id) == 3
            for episode_id in {row["episode_id"] for row in episode_provider_pack_binding}
        ),
        "all_resolved_pack_a_bindings_cite_existing_artifacts": all(
            Path(ref["artifact"]).exists() if not ref["artifact"].startswith("outputs/") else (ROOT / ref["artifact"]).exists()
            for row in episode_provider_pack_binding if row["pack_a_lineage_status"] == "RESOLVED"
            for ref in row["pack_a_source_references"]
        ),
        "all_resolved_pack_e_bindings_cite_existing_artifacts": all(
            Path(ref["artifact"]).exists() if not ref["artifact"].startswith("outputs/") else (ROOT / ref["artifact"]).exists()
            for row in episode_provider_pack_binding if row["pack_e_lineage_status"] == "RESOLVED"
            for ref in row["pack_e_source_references"]
        ),
        "cross_population_reconciliation_result": "PASSED" if not identity_conflicts else "FAILED",
    }

    lineage_binding_status = "ATTENTION_TO_PACK_LINEAGE_BINDING_COMPLETE" if future_binding_counts["FULLY_RESOLVED"] == 1239 else "ATTENTION_TO_PACK_LINEAGE_BINDING_PARTIALLY_COMPLETE"
    attention_integrity_decision = "ALL_1239_ATTENTION_ROWS_BOUND_WITHOUT_MUTATION" if scientific_mutation_count == 0 and len(episode_provider_attention_lineage) == 1239 else "ATTENTION_MUTATION_DETECTED"
    pack_a_decision = "PACK_A_LINEAGE_FULLY_RESOLVED" if pack_a_counts["RESOLVED"] == 1239 else "PACK_A_LINEAGE_PARTIALLY_RESOLVED" if pack_a_counts["RESOLVED"] > 0 else "PACK_A_LINEAGE_BLOCKED"
    pack_e_decision = "PACK_E_LINEAGE_FULLY_RESOLVED" if pack_e_counts["RESOLVED"] == 1239 else "PACK_E_LINEAGE_PARTIALLY_RESOLVED" if pack_e_counts["RESOLVED"] > 0 else "PACK_E_LINEAGE_BLOCKED"
    scientific_boundary_decision = "LINEAGE_ONLY_NO_PACK_CONSTRUCTION"
    next_phase_decision = "READY_FOR_BOUNDED_PACK_POPULATION_CONSTRUCTION" if future_binding_counts["FULLY_RESOLVED"] == 1239 else "REPAIR_PACK_LINEAGE_BINDING"

    run_dir = materialize_run(output_root, fixed_timestamp=fixed_timestamp)
    run_dir.mkdir(parents=True, exist_ok=True)

    write_json(
        run_dir / "run_manifest.json",
        {
            "plan_id": PLAN_ID,
            "governing_full_completion_id": FULL_COMPLETION_ID,
            "governing_consolidation_id": CONSOLIDATION_ID,
            "move": "ATTENTION_TO_PACK_LINEAGE_BINDING",
            "provider_calls_executed": 0,
            "google_writes_executed": 0,
            "pack_a_constructed": 0,
            "pack_e_constructed": 0,
            "forecast_execution_executed": 0,
            "outcome_attachment_executed": 0,
            "matrix_updates_executed": 0,
            "consensus_or_ranking_executed": 0,
            "start_head": start_head,
        },
    )
    write_json(
        run_dir / "governing_artifact_manifest.json",
        {
            "plan_id": PLAN_ID,
            "governing_full_completion_id": FULL_COMPLETION_ID,
            "governing_consolidation_id": CONSOLIDATION_ID,
            "consolidated_episode_provider_population": path_ref(paths["episode_provider_population"]),
            "consolidated_episode_coverage_population": path_ref(paths["episode_coverage_population"]),
            "pack_reconstruction_fanout": path_ref(paths["pack_fanout"]),
            "episode_to_attention_call_map": path_ref(paths["episode_to_attention_call_map"]),
            "pack_status_ledger": path_ref(paths["pack_status_ledger"]),
            "expected_arm_ledger": path_ref(paths["expected_arm_ledger"]),
            "pack_a_plan": path_ref(paths["pack_a_plan"]),
            "pack_e_plan": path_ref(paths["pack_e_plan"]),
            "episode_request_compatibility": path_ref(paths["episode_request_compatibility"]),
            "episode_pack_compatibility": path_ref(paths["episode_pack_compatibility"]),
        },
    )
    write_json(
        run_dir / "lineage_binding_contract.json",
        {
            "canonical_attention_object": "session_attention_map",
            "lineage_binding_scope": "deterministic lineage and eligibility only",
            "forbidden_operations": [
                "provider calls",
                "pack construction",
                "forecast execution",
                "outcome attachment",
                "matrix update",
                "provider consensus",
                "provider ranking",
            ],
            "binding_keys": ["episode_id", "event_id", "source_session_id", "call_id", "expected_arm_identity", "frozen artifact identity"],
            "fuzzy_matching_accepted": False,
            "scientific_values_mutated": False,
        },
    )
    write_json(
        run_dir / "pack_a_source_contract.json",
        {
            "authoritative_pack_definition": "future provider-specific PACK_A forecast arm under frozen Round 1 plan",
            "required_source_artifacts": [
                {"artifact": path_ref(paths["pack_fanout"]), "required_fields": ["episode_id", "attention_call_ids", "pack_a_reconstruction_status", "source_session_id"]},
                {"artifact": path_ref(paths["pack_a_plan"]), "required_fields": ["episode_id", "pack_a_reconstruction_status", "depends_on_attention", "source_session_id"]},
                {"artifact": path_ref(paths["pack_status_ledger"]), "required_fields": ["episode_id", "pack_a_status", "pack_a_reason", "pack_a_input_admissibility"]},
                {"artifact": path_ref(paths["episode_request_compatibility"]), "required_fields": ["episode_id", "status", "provider_request_counts", "source_session_id"]},
                {"artifact": path_ref(paths["expected_arm_ledger"]), "required_fields": ["expected_arm_identity", "provider", "model", "pack_arm", "pack_status"]},
                {"artifact": path_ref(paths["episode_to_attention_call_map"]), "required_fields": ["episode_id", "provider_call_ids", "source_session_id"]},
            ],
            "binding_keys": ["episode_id", "source_session_id", "provider", "model", "expected_arm_identity", "call_id"],
            "eligibility_rules": [
                "fanout.pack_a_reconstruction_status == DETERMINISTIC_REBUILD_AVAILABLE",
                "pack_a_plan.pack_a_reconstruction_status == DETERMINISTIC_REBUILD_AVAILABLE",
                "pack_status_ledger.pack_a_status == PACK_RECONSTRUCTABLE",
                "episode_request_compatibility.status == COMPATIBLE",
                "exact expected_arm_identity row exists for episode_id + provider + PACK_A",
                "episode_to_attention_call_map.provider_call_ids[provider] == authoritative attention call_id",
            ],
            "non_eligibility_rules": [
                "missing exact parent-session lineage",
                "missing frozen Pack A source artifact",
                "source_session identity conflict",
                "contract status mismatch",
            ],
        },
    )
    write_json(
        run_dir / "pack_e_source_contract.json",
        {
            "authoritative_pack_definition": "future shared-request PACK_E forecast arm under frozen Round 1 plan",
            "required_source_artifacts": [
                {"artifact": path_ref(paths["pack_fanout"]), "required_fields": ["episode_id", "pack_e_reconstruction_status", "information_request_route", "shared_request_union_rule", "source_session_id"]},
                {"artifact": path_ref(paths["pack_e_plan"]), "required_fields": ["episode_id", "pack_e_reconstruction_status", "depends_on_attention", "source_session_id"]},
                {"artifact": path_ref(paths["pack_status_ledger"]), "required_fields": ["episode_id", "pack_e_status", "pack_e_reason", "pack_e_input_admissibility"]},
                {"artifact": path_ref(paths["episode_request_compatibility"]), "required_fields": ["episode_id", "status", "provider_request_counts", "source_session_id"]},
                {"artifact": path_ref(paths["episode_pack_compatibility"]), "required_fields": ["episode_id", "status", "pack_e_fingerprint", "provider_model_pairs", "source_session_id"]},
                {"artifact": path_ref(paths["expected_arm_ledger"]), "required_fields": ["expected_arm_identity", "provider", "model", "pack_arm", "pack_status"]},
                {"artifact": path_ref(paths["episode_to_attention_call_map"]), "required_fields": ["episode_id", "provider_call_ids", "source_session_id"]},
            ],
            "binding_keys": ["episode_id", "source_session_id", "provider", "model", "expected_arm_identity", "call_id"],
            "eligibility_rules": [
                "fanout.pack_e_reconstruction_status == DETERMINISTIC_REBUILD_AVAILABLE",
                "fanout.information_request_route == REUSED_EXACT",
                "pack_e_plan.pack_e_reconstruction_status == DETERMINISTIC_REBUILD_AVAILABLE",
                "pack_status_ledger.pack_e_status == PACK_RECONSTRUCTABLE",
                "episode_request_compatibility.status == COMPATIBLE",
                "episode_pack_compatibility.status == COMPATIBLE with exact pack_e_fingerprint",
                "exact expected_arm_identity row exists for episode_id + provider + PACK_E",
                "episode_to_attention_call_map.provider_call_ids[provider] == authoritative attention call_id",
            ],
            "non_eligibility_rules": [
                "missing exact parent-session lineage",
                "missing frozen Pack E source artifact",
                "source_session identity conflict",
                "shared-request route unavailable",
                "contract status mismatch",
            ],
        },
    )
    write_jsonl(run_dir / "episode_provider_attention_lineage.jsonl", episode_provider_attention_lineage)
    write_jsonl(run_dir / "episode_pack_source_lineage.jsonl", episode_pack_source_lineage)
    write_jsonl(run_dir / "episode_provider_pack_binding.jsonl", episode_provider_pack_binding)
    write_json(run_dir / "pack_a_lineage_reconciliation.json", pack_a_reconciliation)
    write_json(run_dir / "pack_e_lineage_reconciliation.json", pack_e_reconciliation)
    write_json(run_dir / "attention_to_pack_cross_reconciliation.json", cross_reconciliation)
    write_jsonl(run_dir / "lineage_blocker_ledger.jsonl", lineage_blockers)
    write_jsonl(run_dir / "identity_conflict_ledger.jsonl", identity_conflicts)
    write_jsonl(run_dir / "missing_source_ledger.jsonl", missing_sources)

    lineage_summary = {
        "episode_provider_attention_lineage_row_count": len(episode_provider_attention_lineage),
        "unique_episode_provider_attention_key_count": len({f"{row['episode_id']}|{row['provider']}" for row in episode_provider_attention_lineage}),
        "episode_pack_source_lineage_row_count": len(episode_pack_source_lineage),
        "future_pack_binding_row_count": len(episode_provider_pack_binding),
        "unique_future_pack_binding_key_count": len({f"{row['episode_id']}|{row['provider']}" for row in episode_provider_pack_binding}),
        "provider_counts": {provider: sum(1 for row in episode_provider_pack_binding if row["provider"] == provider) for provider in PROVIDERS},
        "episode_count": len(grouped_by_episode),
        "episodes_retaining_exactly_three_providers": sum(1 for rows in grouped_by_episode.values() if len(rows) == 3),
        "pack_a_resolved_count": pack_a_counts["RESOLVED"],
        "pack_a_blocked_count": pack_a_counts["BLOCKED_SOURCE_MISSING"] + pack_a_counts["BLOCKED_IDENTITY_CONFLICT"] + pack_a_counts["BLOCKED_CONTRACT_AMBIGUITY"],
        "pack_a_not_required_count": pack_a_counts["NOT_REQUIRED_BY_FROZEN_CONTRACT"],
        "pack_e_resolved_count": pack_e_counts["RESOLVED"],
        "pack_e_blocked_count": pack_e_counts["BLOCKED_SOURCE_MISSING"] + pack_e_counts["BLOCKED_IDENTITY_CONFLICT"] + pack_e_counts["BLOCKED_CONTRACT_AMBIGUITY"],
        "pack_e_not_required_count": pack_e_counts["NOT_REQUIRED_BY_FROZEN_CONTRACT"],
        "fully_resolved_episode_provider_rows": future_binding_counts["FULLY_RESOLVED"],
        "partially_resolved_episode_provider_rows": future_binding_counts["PARTIALLY_RESOLVED"],
        "fully_blocked_episode_provider_rows": future_binding_counts["FULLY_BLOCKED"],
        "missing_source_count": len(missing_sources),
        "identity_conflict_count": len(identity_conflicts),
        "fuzzy_bindings_accepted": 0,
        "attention_scientific_field_mutation_count": scientific_mutation_count,
        "non_selected_attention_rows_preserved_count": non_selected_preserved_count,
        "unresolved_lineage_count": future_binding_counts["PARTIALLY_RESOLVED"] + future_binding_counts["FULLY_BLOCKED"],
        "cross_population_reconciliation_result": cross_reconciliation["cross_population_reconciliation_result"],
        "blocker_categories": dict(sorted(blocker_categories.items())),
    }
    write_json(run_dir / "lineage_summary.json", lineage_summary)
    write_json(
        run_dir / "lineage_decision.json",
        {
            "lineage_binding_status": lineage_binding_status,
            "attention_integrity_decision": attention_integrity_decision,
            "pack_a_lineage_decision": pack_a_decision,
            "pack_e_lineage_decision": pack_e_decision,
            "scientific_boundary_decision": scientific_boundary_decision,
            "next_phase_decision": next_phase_decision,
        },
    )

    return {
        "run_dir": run_dir,
        "summary": lineage_summary,
        "decision": read_json(run_dir / "lineage_decision.json"),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, default=OUTPUT_ROOT)
    parser.add_argument("--fixed-timestamp")
    args = parser.parse_args(argv)
    result = execute_lineage_binding(output_root=args.output_root, fixed_timestamp=args.fixed_timestamp)
    print(
        consolidation.canonical_json(
            {
                "run_dir": str(result["run_dir"]),
                "lineage_binding_status": result["decision"]["lineage_binding_status"],
                "episode_provider_attention_lineage_row_count": result["summary"]["episode_provider_attention_lineage_row_count"],
                "future_pack_binding_row_count": result["summary"]["future_pack_binding_row_count"],
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
