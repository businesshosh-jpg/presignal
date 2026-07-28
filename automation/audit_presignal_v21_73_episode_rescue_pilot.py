#!/usr/bin/env python3
"""Deterministic rescue pilot for the 73 execution-blocked Round 1 Episodes."""
from __future__ import annotations

import argparse
import csv
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

POPULATION_AUDIT_ID = "PPHB-R1-FULL-POPULATION-AUDIT-20260728T125525Z-b25cd178e7d6"
ELIGIBILITY_CONTRACT_ID = "PPHB-R1-ELIGIBILITY-CONTRACT-20260728T132116Z-88a316711419"
ELIGIBILITY_IMPLEMENTATION_ID = "PPHB-R1-ELIGIBILITY-IMPLEMENTATION-20260728T132849Z-297192188403"
RECONSTRUCTION_DRY_RUN_ID = "PPHB-R1-RECONSTRUCTION-DRY-RUN-20260728T134639Z-b3c9532ef93e"

AUDIT_ROOT = ROOT / "outputs" / "presignal_v21_full_round_1_population_audit" / POPULATION_AUDIT_ID
CONTRACT_ROOT = ROOT / "outputs" / "presignal_v21_full_round_1_eligibility_contract" / ELIGIBILITY_CONTRACT_ID
IMPLEMENTATION_ROOT = ROOT / "outputs" / "presignal_v21_full_round_1_eligibility_implementation" / ELIGIBILITY_IMPLEMENTATION_ID
RECONSTRUCTION_ROOT = ROOT / "outputs" / "presignal_v21_full_round_1_reconstruction_dry_run" / RECONSTRUCTION_DRY_RUN_ID
STEP5_ROOT = ROOT / "outputs" / "presignal_v21_step5_reuse"
ATTENTION_ROOT = ROOT / "outputs" / "presignal_v21_attention_preservation"
OUTPUT_ROOT = ROOT / "outputs" / "presignal_v21_73_execution_blocked_episode_rescue"

SEED = "20260728"
SAMPLE_SIZE = 9
STANDALONE_TARGET = 3
BATCH_TARGET = 3

CLASSIFICATIONS = {
    "RECOVERABLE_EXACT",
    "RECOVERABLE_BY_DETERMINISTIC_LINK_REPAIR",
    "PARTIAL_LINEAGE_ONLY",
    "HISTORICAL_VERSION_UNVERIFIED",
    "NO_RECOVERY_ROUTE",
}


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def fingerprint(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


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


def write_csv(path: Path, rows: list[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("")
        return
    fieldnames = sorted({key for row in rows for key in row.keys()})
    temp = path.with_suffix(path.suffix + ".tmp")
    with temp.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    os.replace(temp, path)


def path_ref(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def git_head() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()


def artifact_allowed_as_historical_evidence(path: Path) -> bool:
    text = path_ref(path)
    if "outputs/" not in text:
        return False
    if "docs/" in text:
        return False
    return True


def exact_only_join(left: str, right: str) -> bool:
    return bool(left) and left == right


def fuzzy_join_rejected(left: str, right: str) -> bool:
    return not exact_only_join(left, right)


def load_episode_rows() -> dict[str, dict[str, Any]]:
    rows = read_jsonl(ROOT / "outputs" / "presignal_v21_episode_builder" / "episode_rows.jsonl")
    return {row["episode_id"]: row for row in rows}


def load_blocked_73() -> list[dict[str, Any]]:
    contract_rows = {
        row["episode_id"]: row
        for row in read_jsonl(CONTRACT_ROOT / "full_population_contract_application.jsonl")
    }
    blocked_rows = read_jsonl(RECONSTRUCTION_ROOT / "unavailable_73_blocker_ledger.jsonl")
    episode_rows = load_episode_rows()
    merged: list[dict[str, Any]] = []
    for row in blocked_rows:
        episode_id = row["episode_id"]
        episode = episode_rows[episode_id]
        contract = contract_rows[episode_id]
        merged.append(
            {
                "episode_id": episode_id,
                "release_ts": contract["release_ts"],
                "forecast_cutoff_ts": episode["forecast_cutoff_ts"],
                "episode_type": "BATCH" if episode["same_time_cluster_flag"] else "STANDALONE",
                "member_event_count": episode["member_event_count"],
                "member_event_ids": list(episode["member_event_ids"]),
                "member_indicator_names": list(episode["member_indicator_names"]),
                "event_family": contract["event_family"],
                "original_blocker": row["source_session_reason"] or row["blocking_layer"],
                "blocking_layer": row["blocking_layer"],
                "attention_status": row["attention_status"],
                "pack_a_status": row["pack_a_status"],
                "pack_e_status": row["pack_e_status"],
                "historical_source_lineage_status": row["historical_source_lineage_status"],
                "baseline_source_path": path_ref(RECONSTRUCTION_ROOT / "unavailable_73_blocker_ledger.jsonl"),
            }
        )
    merged.sort(key=lambda row: (row["release_ts"], row["episode_id"]))
    return merged


def rank_hex(seed: str, salt: str, episode_id: str) -> str:
    return hashlib.sha256(f"{seed}|{salt}|{episode_id}".encode("utf-8")).hexdigest()


def coverage_key(row: Mapping[str, Any]) -> tuple[str, int]:
    return (str(row["release_ts"])[:7], int(row["member_event_count"]))


def sample_blocked_population(rows: list[dict[str, Any]], seed: str = SEED) -> dict[str, Any]:
    by_id = {row["episode_id"]: row for row in rows}
    if len(rows) != 73:
        raise ValueError("BLOCKED_SOURCE_POOL_NOT_73")
    if len(by_id) != 73:
        raise ValueError("BLOCKED_SOURCE_POOL_DUPLICATE_EPISODES")

    standalone = [
        {
            **row,
            "selection_rank_hex": rank_hex(seed, "standalone", row["episode_id"]),
        }
        for row in rows
        if row["episode_type"] == "STANDALONE"
    ]
    batch = [
        {
            **row,
            "selection_rank_hex": rank_hex(seed, "batch", row["episode_id"]),
        }
        for row in rows
        if row["episode_type"] == "BATCH"
    ]
    standalone.sort(key=lambda row: (row["selection_rank_hex"], row["release_ts"], row["episode_id"]))
    batch.sort(key=lambda row: (row["selection_rank_hex"], row["release_ts"], row["episode_id"]))

    selected = standalone[:STANDALONE_TARGET] + batch[:BATCH_TARGET]
    selected_ids = {row["episode_id"] for row in selected}

    counts = Counter(coverage_key(row) for row in rows)
    covered = {coverage_key(row) for row in selected}
    additional_pool = []
    for row in rows:
        if row["episode_id"] in selected_ids:
            continue
        additional_pool.append(
            {
                **row,
                "selection_rank_hex": rank_hex(seed, "coverage", row["episode_id"]),
                "coverage_key": coverage_key(row),
                "coverage_count": counts[coverage_key(row)],
                "adds_new_coverage": coverage_key(row) not in covered,
            }
        )
    additional_pool.sort(
        key=lambda row: (
            not row["adds_new_coverage"],
            row["coverage_count"],
            row["selection_rank_hex"],
            row["release_ts"],
            row["episode_id"],
        )
    )

    selected.extend(additional_pool[:3])
    selected.sort(key=lambda row: (row["release_ts"], row["episode_id"]))
    if len(selected) != SAMPLE_SIZE:
        raise ValueError("SAMPLE_SIZE_NOT_NINE")
    if sum(row["episode_type"] == "STANDALONE" for row in selected) < STANDALONE_TARGET:
        raise ValueError("STANDALONE_TARGET_NOT_MET")
    if sum(row["episode_type"] == "BATCH" for row in selected) < BATCH_TARGET:
        raise ValueError("BATCH_TARGET_NOT_MET")

    ranked_order = [
        {"selection_bucket": "standalone", **row}
        for row in standalone
    ] + [
        {"selection_bucket": "batch", **row}
        for row in batch
    ] + [
        {"selection_bucket": "coverage", **row}
        for row in additional_pool
    ]

    replacement_order = [
        row for row in additional_pool[3:]
    ]

    return {
        "sample": selected,
        "ranked_order": ranked_order,
        "replacement_order": replacement_order,
        "sampling_algorithm": (
            "Seeded exact-identity stratified ranking: first 3 STANDALONE by sha256(seed|standalone|episode_id), "
            "first 3 BATCH by sha256(seed|batch|episode_id), then 3 additional rows chosen from the remainder "
            "to maximize uncovered (release_month, member_event_count) patterns, breaking ties by "
            "sha256(seed|coverage|episode_id)."
        ),
        "sampling_strata": {
            "required_minimums": {
                "STANDALONE": 3,
                "BATCH": 3,
            },
            "coverage_pattern": "(release_month, member_event_count)",
            "blocker_pattern": "NO_EXACT_PARENT_SESSION",
        },
    }


def build_source_inventory() -> list[dict[str, Any]]:
    candidate_paths = [
        ROOT / "outputs" / "presignal_v21_episode_builder" / "episode_rows.jsonl",
        STEP5_ROOT / "episode_parent_session_map.jsonl",
        STEP5_ROOT / "episode_attention_compatibility.jsonl",
        STEP5_ROOT / "episode_request_compatibility.jsonl",
        STEP5_ROOT / "episode_pack_compatibility.jsonl",
        STEP5_ROOT / "compatibility_unavailable_ledger.jsonl",
        STEP5_ROOT / "event_path_forecast_inputs_pack_a.jsonl",
        STEP5_ROOT / "event_path_forecast_inputs_pack_e.jsonl",
        ATTENTION_ROOT / "authoritative_attention_map.jsonl",
        ATTENTION_ROOT / "authoritative_attention_map_manifest.json",
        AUDIT_ROOT / "pack_availability_inventory.jsonl",
        CONTRACT_ROOT / "full_population_contract_application.jsonl",
        IMPLEMENTATION_ROOT / "expected_arm_ledger.jsonl",
        RECONSTRUCTION_ROOT / "unavailable_73_blocker_ledger.jsonl",
        ROOT / "Archive(2).zip",
    ]
    inventory = []
    for path in candidate_paths:
        inventory.append(
            {
                "path": path_ref(path),
                "exists": path.exists(),
                "authorized_historical_evidence": artifact_allowed_as_historical_evidence(path),
                "artifact_kind": path.name,
            }
        )
    return inventory


def load_search_indexes() -> dict[str, Any]:
    episode_rows = load_episode_rows()
    parent_map = {row["episode_id"]: row for row in read_jsonl(STEP5_ROOT / "episode_parent_session_map.jsonl")}
    attention_compat = {row["episode_id"]: row for row in read_jsonl(STEP5_ROOT / "episode_attention_compatibility.jsonl")}
    request_compat = {row["episode_id"]: row for row in read_jsonl(STEP5_ROOT / "episode_request_compatibility.jsonl")}
    pack_compat = {row["episode_id"]: row for row in read_jsonl(STEP5_ROOT / "episode_pack_compatibility.jsonl")}
    pack_inventory = {row["episode_id"]: row for row in read_jsonl(AUDIT_ROOT / "pack_availability_inventory.jsonl")}
    attention_rows = read_jsonl(ATTENTION_ROOT / "authoritative_attention_map.jsonl")
    attention_by_event: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in attention_rows:
        attention_by_event[row["event_id"]].append(row)
    pack_a_rows = read_jsonl(STEP5_ROOT / "event_path_forecast_inputs_pack_a.jsonl")
    pack_e_rows = read_jsonl(STEP5_ROOT / "event_path_forecast_inputs_pack_e.jsonl")
    pack_a_by_session: dict[str, list[dict[str, Any]]] = defaultdict(list)
    pack_e_by_session: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in pack_a_rows:
        pack_a_by_session[row["source_session_id"]].append(row)
    for row in pack_e_rows:
        pack_e_by_session[row["source_session_id"]].append(row)
    return {
        "episode_rows": episode_rows,
        "parent_map": parent_map,
        "attention_compat": attention_compat,
        "request_compat": request_compat,
        "pack_compat": pack_compat,
        "pack_inventory": pack_inventory,
        "attention_by_event": attention_by_event,
        "pack_a_by_session": pack_a_by_session,
        "pack_e_by_session": pack_e_by_session,
    }


def audit_episode(
    sample_row: Mapping[str, Any],
    indexes: Mapping[str, Any],
) -> dict[str, Any]:
    episode_id = sample_row["episode_id"]
    episode_row = indexes["episode_rows"][episode_id]
    parent_row = indexes["parent_map"].get(episode_id, {})
    attention_row = indexes["attention_compat"].get(episode_id, {})
    request_row = indexes["request_compat"].get(episode_id, {})
    pack_row = indexes["pack_compat"].get(episode_id, {})
    inventory_row = indexes["pack_inventory"].get(episode_id, {})

    event_hits: dict[str, list[dict[str, Any]]] = {}
    common_session_ids: set[str] | None = None
    all_three_provider_hits = True
    for event_id in sample_row["member_event_ids"]:
        hits = indexes["attention_by_event"].get(event_id, [])
        event_hits[event_id] = hits
        sessions = {row["session_id"] for row in hits}
        providers = {row["provider"] for row in hits}
        if providers != {"Gemini", "OpenAI", "Anthropic"}:
            all_three_provider_hits = False
        if not hits:
            common_session_ids = set()
            continue
        common_session_ids = sessions if common_session_ids is None else common_session_ids & sessions
    common_session_ids = common_session_ids or set()

    deterministic_session_id = sorted(common_session_ids)[0] if len(common_session_ids) == 1 else ""
    session_has_pack_a = bool(deterministic_session_id and indexes["pack_a_by_session"].get(deterministic_session_id))
    session_has_pack_e = bool(deterministic_session_id and indexes["pack_e_by_session"].get(deterministic_session_id))

    recovered_parent = bool(deterministic_session_id and all_three_provider_hits)
    has_any_attention_event_hit = any(event_hits[event_id] for event_id in sample_row["member_event_ids"])

    exact_parent_chain = bool(parent_row.get("status") == "MATCHED" and parent_row.get("source_session_id"))
    if exact_parent_chain:
        classification = "RECOVERABLE_EXACT"
        repair_rule = ""
    elif recovered_parent and session_has_pack_a and session_has_pack_e:
        classification = "RECOVERABLE_BY_DETERMINISTIC_LINK_REPAIR"
        repair_rule = (
            "Exact repair rule: for every member_event_id in the blocked Episode, require authoritative_attention_map "
            "hits under one identical session_id across Gemini/OpenAI/Anthropic; require that unique session_id to appear "
            "as source_session_id in preserved Pack A and Pack E inputs; then bind the Episode to that exact session_id "
            "without fuzzy matching."
        )
    elif has_any_attention_event_hit or inventory_row.get("historical_source_lineage_status") == "EXISTING_AND_EXACT":
        classification = "PARTIAL_LINEAGE_ONLY"
        repair_rule = ""
    else:
        classification = "NO_RECOVERY_ROUTE"
        repair_rule = ""

    exact_evidence_found = {
        "episode_row_present": True,
        "release_timestamp_exact": exact_only_join(sample_row["release_ts"], episode_row["release_ts"]),
        "forecast_cutoff_exact": exact_only_join(sample_row["forecast_cutoff_ts"], episode_row["forecast_cutoff_ts"]),
        "exact_parent_session_in_parent_map": exact_parent_chain,
        "deterministic_parent_session_from_attention_export": deterministic_session_id,
        "all_member_events_present_in_attention_export": all(event_hits[event_id] for event_id in sample_row["member_event_ids"]),
        "all_member_events_share_one_session_id": len(common_session_ids) == 1,
        "all_member_events_have_all_three_provider_hits": all_three_provider_hits,
        "session_has_exact_pack_a_rows": session_has_pack_a,
        "session_has_exact_pack_e_rows": session_has_pack_e,
        "exact_request_row_present": request_row.get("status") == "COMPATIBLE",
        "exact_pack_row_present": pack_row.get("status") == "COMPATIBLE",
    }
    missing_evidence = []
    if not exact_evidence_found["exact_parent_session_in_parent_map"] and not deterministic_session_id:
        missing_evidence.append("EXACT_PARENT_SESSION_ID")
    if not exact_evidence_found["all_member_events_present_in_attention_export"]:
        missing_evidence.append("FULL_MEMBER_LEVEL_ATTENTION_EVIDENCE")
    if deterministic_session_id and not session_has_pack_a:
        missing_evidence.append("SESSION_LEVEL_PACK_A_LINEAGE")
    if deterministic_session_id and not session_has_pack_e:
        missing_evidence.append("SESSION_LEVEL_PACK_E_LINEAGE")
    if classification in {"PARTIAL_LINEAGE_ONLY", "NO_RECOVERY_ROUTE"} and request_row.get("status") != "COMPATIBLE":
        missing_evidence.append("SESSION_LEVEL_INFORMATION_REQUEST_LINEAGE")

    artifacts_inspected = [
        path_ref(ROOT / "outputs" / "presignal_v21_episode_builder" / "episode_rows.jsonl"),
        path_ref(STEP5_ROOT / "episode_parent_session_map.jsonl"),
        path_ref(STEP5_ROOT / "episode_attention_compatibility.jsonl"),
        path_ref(STEP5_ROOT / "episode_request_compatibility.jsonl"),
        path_ref(STEP5_ROOT / "episode_pack_compatibility.jsonl"),
        path_ref(ATTENTION_ROOT / "authoritative_attention_map.jsonl"),
        path_ref(STEP5_ROOT / "event_path_forecast_inputs_pack_a.jsonl"),
        path_ref(STEP5_ROOT / "event_path_forecast_inputs_pack_e.jsonl"),
        path_ref(AUDIT_ROOT / "pack_availability_inventory.jsonl"),
        path_ref(RECONSTRUCTION_ROOT / "unavailable_73_blocker_ledger.jsonl"),
    ]

    reasoning = (
        "Exact frozen Episode identity, release timestamp, and cutoff are present. "
        + (
            f"A unique historical session `{deterministic_session_id}` is provable from authoritative Attention hits "
            "and preserved Pack A/E session rows."
            if classification == "RECOVERABLE_BY_DETERMINISTIC_LINK_REPAIR"
            else "No complete exact parent-session chain is provable from preserved artifacts."
        )
    )

    promotion_recommendation = (
        "INCLUDE_IN_FULL_73_RESCUE_CONTRACT"
        if classification in {"RECOVERABLE_EXACT", "RECOVERABLE_BY_DETERMINISTIC_LINK_REPAIR"}
        else "REMAIN_BLOCKED_PENDING_BROADER_SOURCE_RECOVERY"
    )

    return {
        "episode_id": episode_id,
        "episode_type": sample_row["episode_type"],
        "release_ts": sample_row["release_ts"],
        "member_event_count": sample_row["member_event_count"],
        "member_event_ids": list(sample_row["member_event_ids"]),
        "original_blocker": sample_row["original_blocker"],
        "artifacts_inspected": artifacts_inspected,
        "exact_evidence_found": exact_evidence_found,
        "missing_evidence": missing_evidence,
        "recovery_classification": classification,
        "deterministic_repair_rule": repair_rule,
        "reasoning_summary": reasoning,
        "promotion_recommendation": promotion_recommendation,
        "deterministic_session_id_candidate": deterministic_session_id,
        "event_hit_counts": {event_id: len(event_hits[event_id]) for event_id in sample_row["member_event_ids"]},
    }


def build_run(*, output_root: Path = OUTPUT_ROOT, fixed_timestamp: str | None = None) -> dict[str, Any]:
    baseline_rows = load_blocked_73()
    sample_spec = sample_blocked_population(baseline_rows)
    sampled_rows = sample_spec["sample"]
    indexes = load_search_indexes()
    ts = fixed_timestamp or now()
    seed_payload = {
        "seed": SEED,
        "source_population_fingerprint": fingerprint(baseline_rows),
        "sample_ids": [row["episode_id"] for row in sampled_rows],
        "timestamp": ts,
    }
    run_id = (
        "PPHB-R1-73-EPISODE-RESCUE-PILOT-"
        + ts.replace(":", "").replace("-", "")
        + "-"
        + hashlib.sha256(canonical_json(seed_payload).encode("utf-8")).hexdigest()[:12]
    )
    run_dir = output_root / run_id

    source_inventory = build_source_inventory()
    artifact_search_ledger: list[dict[str, Any]] = []
    parent_audit: list[dict[str, Any]] = []
    lineage_audit: list[dict[str, Any]] = []
    classifications: list[dict[str, Any]] = []

    for sample_row in sampled_rows:
        audit = audit_episode(sample_row, indexes)
        classification = audit["recovery_classification"]
        if classification not in CLASSIFICATIONS:
            raise ValueError("UNKNOWN_CLASSIFICATION")

        episode_id = sample_row["episode_id"]
        for artifact in audit["artifacts_inspected"]:
            artifact_search_ledger.append(
                {
                    "episode_id": episode_id,
                    "artifact_path": artifact,
                    "exact_episode_id_search": True,
                    "exact_member_event_id_search": True,
                    "fuzzy_matching_used": False,
                }
            )
        parent_audit.append(
            {
                "episode_id": episode_id,
                "release_ts": sample_row["release_ts"],
                "original_parent_status": "UNAVAILABLE",
                "deterministic_session_id_candidate": audit["deterministic_session_id_candidate"],
                "parent_session_recovery_status": (
                    "RECOVERED_BY_DETERMINISTIC_LINK_REPAIR"
                    if classification == "RECOVERABLE_BY_DETERMINISTIC_LINK_REPAIR"
                    else "NOT_RECOVERED"
                ),
            }
        )
        lineage_audit.append(
            {
                "episode_id": episode_id,
                "release_ts": sample_row["release_ts"],
                "classification": classification,
                "all_member_events_share_one_session_id": audit["exact_evidence_found"]["all_member_events_share_one_session_id"],
                "all_member_events_have_all_three_provider_hits": audit["exact_evidence_found"]["all_member_events_have_all_three_provider_hits"],
                "session_has_exact_pack_a_rows": audit["exact_evidence_found"]["session_has_exact_pack_a_rows"],
                "session_has_exact_pack_e_rows": audit["exact_evidence_found"]["session_has_exact_pack_e_rows"],
            }
        )
        classifications.append(
            {
                "episode_id": episode_id,
                "recovery_classification": classification,
                "deterministic_repair_rule": audit["deterministic_repair_rule"],
                "promotion_recommendation": audit["promotion_recommendation"],
            }
        )
        write_json(run_dir / "sample_case_reports" / f"{episode_id}.json", audit)

    classification_counts = Counter(row["recovery_classification"] for row in classifications)
    recoverable_count = classification_counts["RECOVERABLE_EXACT"] + classification_counts["RECOVERABLE_BY_DETERMINISTIC_LINK_REPAIR"]
    if recoverable_count >= 7:
        recovery_result = "BROAD_RECOVERY_ROUTE_SUPPORTED"
        next_step = "FREEZE_FULL_73_RESCUE_CONTRACT"
    elif recoverable_count >= 3:
        recovery_result = "SUBGROUP_RECOVERY_ROUTE_SUPPORTED"
        next_step = "AUDIT_FULL_73_BY_RECOVERY_PATTERN"
    else:
        recovery_result = "BROAD_RECOVERY_ROUTE_NOT_SUPPORTED"
        next_step = "LEAVE_73_ADMITTED_AND_BLOCKED"

    pilot_summary = {
        "rescue_pilot_status": "RESCUE_PILOT_COMPLETE",
        "recovery_result": recovery_result,
        "main_path_impact_decision": "MAIN_341_PATH_UNCHANGED",
        "next_step_decision": next_step,
        "blocked_source_population_count": len(baseline_rows),
        "sample_size": len(sampled_rows),
        "seed": SEED,
        "sampled_episode_ids": [row["episode_id"] for row in sampled_rows],
        "classification_counts": dict(sorted(classification_counts.items())),
        "recoverable_count": recoverable_count,
    }
    pilot_decision = {
        "rescue_pilot_status": "RESCUE_PILOT_COMPLETE",
        "recovery_result": recovery_result,
        "main_path_impact_decision": "MAIN_341_PATH_UNCHANGED",
        "next_step_decision": next_step,
        "reasoning": [
            "The 341-Episode main path stays unchanged because this rescue only audits the admitted-but-blocked 73.",
            "Recoverability requires exact preserved lineage, not plausible reconstruction.",
            "Sample classifications are driven by exact member-level event hits, exact session reuse, and exact Pack-session bindings only.",
        ],
    }

    drift_authorization = {
        "authorized_drift": "73 Execution-Blocked Episodes Rescue",
        "move": "R1",
        "external_calls": {
            "provider": 0,
            "research_ai": 0,
            "market_data": 0,
            "web": 0,
            "google_writes": 0,
        },
    }
    sampling_contract = {
        "source_population_artifact": path_ref(RECONSTRUCTION_ROOT / "unavailable_73_blocker_ledger.jsonl"),
        "source_population_fingerprint": fingerprint(baseline_rows),
        "source_population_ids": [row["episode_id"] for row in baseline_rows],
        "random_seed": SEED,
        "sample_size": SAMPLE_SIZE,
        "sampling_algorithm": sample_spec["sampling_algorithm"],
        "sampling_strata": sample_spec["sampling_strata"],
        "ranked_selection_order": sample_spec["ranked_order"],
        "selected_episode_ids": [row["episode_id"] for row in sampled_rows],
        "replacement_order": sample_spec["replacement_order"],
        "manual_substitution_allowed": False,
    }

    write_json(run_dir / "run_manifest.json", {
        "run_id": run_id,
        "move": "R1",
        "kind": "73_EXECUTION_BLOCKED_EPISODE_RESCUE_PILOT",
        "created_ts": ts,
        "git_head": git_head(),
        "governing_artifacts": {
            "population_audit": POPULATION_AUDIT_ID,
            "eligibility_contract": ELIGIBILITY_CONTRACT_ID,
            "eligibility_implementation": ELIGIBILITY_IMPLEMENTATION_ID,
            "reconstruction_dry_run": RECONSTRUCTION_DRY_RUN_ID,
        },
        "external_calls": {
            "provider": 0,
            "research_ai": 0,
            "market_data": 0,
            "web": 0,
            "google_writes": 0,
        },
    })
    write_json(run_dir / "drift_authorization.json", drift_authorization)
    write_json(run_dir / "sampling_contract.json", sampling_contract)
    write_jsonl(run_dir / "blocked_73_baseline.jsonl", baseline_rows)
    write_jsonl(run_dir / "sampled_episode_manifest.jsonl", sampled_rows)
    write_json(run_dir / "source_inventory.json", source_inventory)
    write_jsonl(run_dir / "artifact_search_ledger.jsonl", artifact_search_ledger)
    write_jsonl(run_dir / "parent_session_recovery_audit.jsonl", parent_audit)
    write_jsonl(run_dir / "lineage_recovery_audit.jsonl", lineage_audit)
    write_jsonl(run_dir / "recovery_classification.jsonl", classifications)
    write_json(run_dir / "pilot_summary.json", pilot_summary)
    write_json(run_dir / "pilot_decision.json", pilot_decision)
    write_csv(run_dir / "sampled_episode_manifest.csv", sampled_rows)
    write_csv(run_dir / "recovery_classification.csv", classifications)

    return {
        "run_id": run_id,
        "run_dir": run_dir,
        "pilot_summary": pilot_summary,
        "sampling_contract": sampling_contract,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, default=OUTPUT_ROOT)
    parser.add_argument("--fixed-timestamp")
    args = parser.parse_args()
    result = build_run(output_root=args.output_root, fixed_timestamp=args.fixed_timestamp)
    print(canonical_json({"run_id": result["run_id"], **result["pilot_summary"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
