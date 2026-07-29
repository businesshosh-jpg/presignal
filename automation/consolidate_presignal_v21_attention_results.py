#!/usr/bin/env python3
"""Consolidate the completed historical Attention population without changing scientific values."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from automation import execute_presignal_v21_attention_batch_001 as batch001
from automation import execute_presignal_v21_attention_batch_004 as batch004

PLAN_ID = batch004.PLAN_ID
PLAN_ROOT = batch004.PLAN_ROOT
FULL_COMPLETION_ID = "PPHB-R1-ATTENTION-EXECUTION-FULL-COMPLETION-20260729T095829Z-0437a6002810"
EXECUTION_OUTPUT_ROOT = batch004.OUTPUT_ROOT
CONSOLIDATION_OUTPUT_ROOT = ROOT / "outputs" / "presignal_v21_full_round_1_attention_consolidation"
EPISODE_PARENT_SESSION_MAP = ROOT / "outputs" / "presignal_v21_step5_reuse" / "episode_parent_session_map.jsonl"
EPISODE_ROWS = ROOT / "outputs" / "presignal_v21_episode_builder" / "episode_rows.jsonl"
BLOCKED_EPISODE_RESCUE_ROOT = ROOT / "outputs" / "presignal_v21_73_execution_blocked_episode_rescue"

BLOCKED_RUN_IDS = {
    "PPHB-R1-ATTENTION-EXECUTION-BATCHES-015-016-20260729T090318Z-9e64f5d6f733",
    "PPHB-R1-ATTENTION-EXECUTION-BATCH-015-20260729T090319Z-a624a4386240",
}


class ConsolidationError(RuntimeError):
    pass


def canonical_json(value: Any) -> str:
    return batch004.canonical_json(value)


def write_json(path: Path, value: Any) -> None:
    batch004.write_json(path, value)


def write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    batch004.write_jsonl(path, rows)


def now() -> str:
    return batch004.now()


def path_ref(path: Path) -> str:
    return batch004.path_ref(path)


def read_json(path: Path) -> dict[str, Any]:
    return batch004.read_json(path)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return batch004.read_jsonl(path)


def sha256_row(row: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(row).encode("utf-8")).hexdigest()


def materialize_run(output_root: Path, fixed_timestamp: str | None = None) -> Path:
    ts = fixed_timestamp or now()
    seed = {"plan_id": PLAN_ID, "full_completion_id": FULL_COMPLETION_ID, "timestamp": ts, "move": "ATTENTION_RESULT_CONSOLIDATION"}
    run_id = (
        "PPHB-R1-ATTENTION-RESULT-CONSOLIDATION-"
        + ts.replace(":", "").replace("-", "")
        + "-"
        + hashlib.sha256(canonical_json(seed).encode("utf-8")).hexdigest()[:12]
    )
    return output_root / run_id


def first_existing_path(run_dir: Path, candidates: list[str]) -> Path:
    for candidate in candidates:
        path = run_dir / candidate
        if path.exists():
            return path
    raise ConsolidationError(f"MISSING_EXPECTED_ARTIFACT:{run_dir}")


def load_authoritative_inventory() -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, dict[str, Any]]]:
    completion_root = EXECUTION_OUTPUT_ROOT / FULL_COMPLETION_ID
    call_rows = read_jsonl(completion_root / "call_completion_reconciliation.jsonl")
    batch_rows = read_jsonl(completion_root / "authoritative_batch_result_inventory.jsonl")
    batch_by_id = {row["batch_id"]: row for row in batch_rows}
    return call_rows, batch_rows, batch_by_id


def load_plan_call_ledger() -> dict[str, dict[str, Any]]:
    return {row["call_id"]: row for row in read_jsonl(PLAN_ROOT / "attention_call_ledger.jsonl")}


def load_sessions_and_members() -> tuple[dict[str, dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    return batch001.read_source_sessions()


def load_episode_inventory() -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    parent_rows = {row["episode_id"]: row for row in read_jsonl(EPISODE_PARENT_SESSION_MAP)}
    episode_rows = {row["episode_id"]: row for row in read_jsonl(EPISODE_ROWS)}
    rescue_runs = sorted([path for path in BLOCKED_EPISODE_RESCUE_ROOT.iterdir() if path.is_dir()]) if BLOCKED_EPISODE_RESCUE_ROOT.exists() else []
    rescue_parent_session: dict[str, dict[str, Any]] = {}
    rescue_blocked_rows: dict[str, dict[str, Any]] = {}
    for rescue_run in rescue_runs:
        join_path = rescue_run / "event_date_session_join.jsonl"
        blocked_path = rescue_run / "blocked_73_baseline.jsonl"
        if join_path.exists():
            for row in read_jsonl(join_path):
                rescue_parent_session[row["episode_id"]] = row
        if blocked_path.exists():
            for row in read_jsonl(blocked_path):
                rescue_blocked_rows[row["episode_id"]] = row
    for episode_id, row in rescue_blocked_rows.items():
        selected_session_id = (rescue_parent_session.get(episode_id) or {}).get("selected_session_id")
        parent_rows[episode_id] = {
            "episode_id": episode_id,
            "member_event_ids": list(row.get("member_event_ids") or []),
            "reason": row.get("original_blocker") or row.get("blocking_layer") or "",
            "release_ts": row.get("release_ts"),
            "source_session_id": selected_session_id or parent_rows.get(episode_id, {}).get("source_session_id", ""),
            "status": "RESCUED_EXACT_EVENT_DATE_LINK",
        }
        episode_rows.setdefault(
            episode_id,
            {
                "episode_id": episode_id,
                "release_ts": row.get("release_ts"),
                "member_event_ids": list(row.get("member_event_ids") or []),
                "primary_event_id": (row.get("member_event_ids") or [None])[0],
                "episode_family": row.get("episode_type"),
            },
        )
    return parent_rows, episode_rows


def load_run_artifacts(run_id: str) -> dict[str, Path]:
    run_dir = EXECUTION_OUTPUT_ROOT / run_id
    return {
        "run_dir": run_dir,
        "normalized": first_existing_path(run_dir, ["normalized_attention_results.jsonl", "final_normalized_attention_results.jsonl"]),
        "episode_map": first_existing_path(run_dir, ["episode_attention_result_map.jsonl", "final_episode_attention_result_map.jsonl"]),
        "provider_authority": run_dir / "provider_authority_results.jsonl",
        "raw_provider_outputs": run_dir / "raw_provider_outputs.jsonl",
        "raw_transport_results": run_dir / "raw_transport_results.jsonl",
        "decision": first_existing_path(run_dir, ["batch_decision.json", "batch_001_decision.json", "batch_002_decision.json", "batch_003_decision.json"]),
        "summary": first_existing_path(run_dir, ["batch_summary.json", "batch_001_summary.json", "batch_002_summary.json", "batch_003_summary.json"]),
    }


def scientific_rows_from_authoritative_row(row: Mapping[str, Any]) -> list[dict[str, Any]]:
    if "validated_attention_rows" in row:
        return [dict(item) for item in row["validated_attention_rows"]]
    if "attention_result" in row and isinstance(row["attention_result"], Mapping):
        return [dict(item) for item in row["attention_result"].get("attention_items", [])]
    raise ConsolidationError("AUTHORITATIVE_RESULT_SHAPE_UNSUPPORTED")


def raw_claimed_provider_from_authoritative_row(row: Mapping[str, Any]) -> Any:
    if "attention_result" in row and isinstance(row["attention_result"], Mapping):
        norm = row["attention_result"].get("_provider_identity_normalization") or {}
        return norm.get("original_provider") or row["attention_result"].get("provider")
    scientific_rows = scientific_rows_from_authoritative_row(row)
    for item in scientific_rows:
        norm = item.get("provider_identity_normalization") or {}
        if isinstance(norm, Mapping) and norm.get("raw_claimed_provider") is not None:
            return norm.get("raw_claimed_provider")
        if isinstance(norm, Mapping) and norm.get("original_provider") is not None:
            return norm.get("original_provider")
    if scientific_rows:
        return scientific_rows[0].get("provider")
    return None


def raw_evidence_references_for_call(run_id: str, authoritative_row: Mapping[str, Any], artifacts: Mapping[str, Path]) -> list[str]:
    refs: list[str] = []
    if artifacts["raw_provider_outputs"].exists():
        refs.append(path_ref(artifacts["raw_provider_outputs"]))
    if artifacts["raw_transport_results"].exists():
        refs.append(path_ref(artifacts["raw_transport_results"]))
    if artifacts["provider_authority"].exists():
        refs.append(path_ref(artifacts["provider_authority"]))
    if not refs:
        refs.append(path_ref(artifacts["normalized"]))
    if authoritative_row.get("source_live_run_identity"):
        refs.append(str(authoritative_row["source_live_run_identity"]))
    if authoritative_row.get("source_repair_run_identity"):
        refs.append(str(authoritative_row["source_repair_run_identity"]))
    return refs


def classify_lineage_run(run_id: str) -> str:
    if run_id in BLOCKED_RUN_IDS:
        return "BLOCKED"
    if "CONTRACT-REPAIR" in run_id or "FAILURE-AUDIT" in run_id or "AUTHORITY-AUDIT" in run_id or "ROW-STATUS-AUDIT" in run_id or "SHADOW-ALIAS-AUDIT" in run_id:
        return "REPAIR"
    if "COMPLETENESS-RETRY" in run_id or "CORRECTED-FINALIZATION" in run_id:
        return "RETRY"
    if "FINALIZATION" in run_id:
        return "FAILED_OR_PARTIAL_EXECUTION_EVIDENCE"
    if "AUTH-RECOVERY" in run_id:
        return "AUTHENTICATION_RECOVERY_COORDINATION"
    if "EXECUTION-BATCH" in run_id or "BATCH-" in run_id:
        return "EXECUTION_EVIDENCE"
    return "OTHER_EVIDENCE"


def build_call_lineage(
    authoritative_call: Mapping[str, Any],
    authoritative_row: Mapping[str, Any],
    batch_inventory_row: Mapping[str, Any],
) -> dict[str, Any]:
    run_ids: list[str] = []
    for value in [
        authoritative_row.get("source_live_run_identity"),
        authoritative_row.get("source_repair_run_identity"),
        *authoritative_call.get("non_authoritative_evidence_runs", []),
        authoritative_call["authoritative_run_id"],
    ]:
        if value and value not in run_ids:
            run_ids.append(str(value))
    run_states = [{"run_id": run_id, "state": classify_lineage_run(run_id)} for run_id in run_ids]
    blocked_refs = [run_id for run_id in run_ids if classify_lineage_run(run_id) == "BLOCKED"]
    repair_refs = [run_id for run_id in run_ids if classify_lineage_run(run_id) == "REPAIR"]
    retry_refs = [run_id for run_id in run_ids if classify_lineage_run(run_id) == "RETRY"]
    failed_refs = [run_id for run_id in run_ids if classify_lineage_run(run_id) == "FAILED_OR_PARTIAL_EXECUTION_EVIDENCE"]
    return {
        "call_id": authoritative_call["call_id"],
        "all_known_run_identities": run_ids,
        "all_known_states": sorted({row["state"] for row in run_states}),
        "run_state_inventory": run_states,
        "blocked_evidence_references": blocked_refs,
        "failed_evidence_references": failed_refs,
        "repair_references": repair_refs,
        "retry_references": retry_refs,
        "final_authoritative_run_identity": authoritative_call["authoritative_run_id"],
        "authoritative_selection_reason": "GOVERNING_FULL_COMPLETION_RECONCILIATION",
        "double_count_prevention_decision": "AUTHORITATIVE_RESULT_ONLY",
        "batch_inventory_kind": batch_inventory_row["kind"],
    }


def provider_row_key(source_session_id: str, provider: str) -> str:
    return f"{source_session_id}|{provider}"


def episode_provider_key(episode_id: str, provider: str) -> str:
    return f"{episode_id}|{provider}"


def session_member_name(member: Mapping[str, Any]) -> str | None:
    for key in ("indicator", "indicator_name", "event_name", "primary_indicator_name"):
        value = member.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def scientific_event_name(
    scientific_row: Mapping[str, Any],
    session_member_by_event_id: Mapping[str, Mapping[str, Any]],
) -> str | None:
    event_id = scientific_row.get("event_id")
    if event_id is not None:
        member = session_member_by_event_id.get(str(event_id))
        if member is not None:
            return session_member_name(member)
    return None


def execute_consolidation(
    *,
    output_root: Path = CONSOLIDATION_OUTPUT_ROOT,
    fixed_timestamp: str | None = None,
) -> dict[str, Any]:
    start_head = batch004.git_head()
    call_inventory, batch_inventory, batch_by_id = load_authoritative_inventory()
    if len(call_inventory) != 204:
        raise ConsolidationError("AUTHORITATIVE_CALL_COUNT_MISMATCH")
    if len({row["call_id"] for row in call_inventory}) != 204:
        raise ConsolidationError("AUTHORITATIVE_CALL_ID_DUPLICATE")
    if any(row["completion_status"] != "VALIDATED" for row in call_inventory):
        raise ConsolidationError("NON_VALIDATED_CALL_PRESENT")

    call_ledger = load_plan_call_ledger()
    sessions_by_id, members_by_session = load_sessions_and_members()
    parent_by_episode, episode_rows_by_id = load_episode_inventory()

    run_dir = materialize_run(output_root, fixed_timestamp=fixed_timestamp)
    run_dir.mkdir(parents=True, exist_ok=True)

    authoritative_call_inventory: list[dict[str, Any]] = []
    call_lineage_ledger: list[dict[str, Any]] = []
    session_provider_population: list[dict[str, Any]] = []
    episode_provider_population: list[dict[str, Any]] = []
    episode_coverage_population: list[dict[str, Any]] = []
    call_to_episode_provider_map: list[dict[str, Any]] = []
    session_provider_reconciliation: list[dict[str, Any]] = []
    episode_provider_reconciliation: list[dict[str, Any]] = []
    duplicate_conflicts: list[dict[str, Any]] = []
    missing_mapping_rows: list[dict[str, Any]] = []
    unexpected_mapping_rows: list[dict[str, Any]] = []

    run_artifact_cache: dict[str, dict[str, Path]] = {}
    normalized_rows_by_call: dict[str, dict[str, Any]] = {}
    provider_authority_by_call: dict[str, dict[str, Any]] = {}

    for batch_row in batch_inventory:
        artifacts = load_run_artifacts(batch_row["run_id"])
        run_artifact_cache[batch_row["run_id"]] = artifacts
        for row in read_jsonl(artifacts["normalized"]):
            normalized_rows_by_call[row["call_id"]] = row
        if artifacts["provider_authority"].exists():
            for row in read_jsonl(artifacts["provider_authority"]):
                provider_authority_by_call[row["call_id"]] = row

    session_provider_keys: set[str] = set()
    episode_provider_keys: set[str] = set()
    call_id_keys: set[str] = set()
    provider_episode_counts: Counter[str] = Counter()
    provider_call_counts: Counter[str] = Counter()
    sessions_seen: set[str] = set()
    episode_ids_seen: set[str] = set()
    scientific_mutation_count = 0
    lineage_conflict_count = 0

    for call_row in call_inventory:
        call_id = call_row["call_id"]
        if call_id in call_id_keys:
            duplicate_conflicts.append({"conflict_type": "CALL_ID_DUPLICATE", "call_id": call_id})
            continue
        call_id_keys.add(call_id)

        ledger_row = call_ledger.get(call_id)
        if ledger_row is None:
            raise ConsolidationError("CALL_LEDGER_ROW_MISSING")
        batch_row = batch_by_id[call_row["batch_id"]]
        authoritative_row = normalized_rows_by_call.get(call_id)
        if authoritative_row is None:
            raise ConsolidationError("AUTHORITATIVE_NORMALIZED_RESULT_MISSING")
        artifacts = run_artifact_cache[call_row["authoritative_run_id"]]
        scientific_rows = scientific_rows_from_authoritative_row(authoritative_row)
        scientific_by_event_id = {str(item.get("event_id")): item for item in scientific_rows if item.get("event_id") is not None}
        raw_claimed_provider_value = provider_authority_by_call.get(call_id, {}).get("raw_claimed_provider")
        if raw_claimed_provider_value is None:
            raw_claimed_provider_value = raw_claimed_provider_from_authoritative_row(authoritative_row)
        source_session_id = call_row["source_session_id"]
        session_payload = sessions_by_id[source_session_id]
        session_members = members_by_session.get(source_session_id, [])
        session_member_by_event_id = {str(member.get("event_id")): member for member in session_members if member.get("event_id") is not None}
        session_event_id_by_name = {
            name: event_id
            for event_id, member in session_member_by_event_id.items()
            if (name := session_member_name(member)) is not None
        }
        region = source_session_id.split("|")[0]
        session_date = source_session_id.split("|")[1]
        provider = call_row["provider"]
        model = call_row["model"]
        sessions_seen.add(source_session_id)
        provider_call_counts[f"{provider}|{model}"] += 1

        lineage_row = build_call_lineage(call_row, authoritative_row, batch_row)
        blocked_refs = lineage_row["blocked_evidence_references"]
        if call_row["authoritative_run_id"] in BLOCKED_RUN_IDS:
            lineage_conflict_count += 1
            duplicate_conflicts.append({"conflict_type": "BLOCKED_RUN_MARKED_AUTHORITATIVE", "call_id": call_id, "run_id": call_row["authoritative_run_id"]})
        if len([run_id for run_id in lineage_row["all_known_run_identities"] if run_id == call_row["authoritative_run_id"]]) != 1:
            lineage_conflict_count += 1
            duplicate_conflicts.append({"conflict_type": "AUTHORITATIVE_LINEAGE_DUPLICATE", "call_id": call_id})
        call_lineage_ledger.append(lineage_row)

        call_level_row = {
            "call_id": call_id,
            "batch_id": call_row["batch_id"],
            "authoritative_run_identity": call_row["authoritative_run_id"],
            "source_session_id": source_session_id,
            "session_date": session_date,
            "session_region": region,
            "provider": provider,
            "model": model,
            "cutoff": session_payload["forecast_cutoff"],
            "input_fingerprint": authoritative_row.get("request_fingerprint"),
            "expected_event_count": len(call_row["episode_ids"]),
            "returned_event_count": len(call_row["episode_ids"]),
            "raw_validated_attention_row_count": len(scientific_rows),
            "validation_state": call_row["completion_status"],
            "raw_claimed_provider_value": raw_claimed_provider_value,
            "raw_evidence_references": raw_evidence_references_for_call(call_row["authoritative_run_id"], authoritative_row, artifacts),
            "normalized_result_reference": path_ref(artifacts["normalized"]),
            "repair_retry_lineage": {
                "repair_references": lineage_row["repair_references"],
                "retry_references": lineage_row["retry_references"],
                "blocked_evidence_references": blocked_refs,
                "failed_evidence_references": lineage_row["failed_evidence_references"],
            },
        }
        authoritative_call_inventory.append(call_level_row)

        sp_key = provider_row_key(source_session_id, provider)
        if sp_key in session_provider_keys:
            duplicate_conflicts.append({"conflict_type": "SESSION_PROVIDER_DUPLICATE", "key": sp_key, "call_id": call_id})
            continue
        session_provider_keys.add(sp_key)

        session_provider_population.append(
            {
                "source_session_id": source_session_id,
                "provider": provider,
                "model": model,
                "call_id": call_id,
                "batch_id": call_row["batch_id"],
                "authoritative_run_identity": call_row["authoritative_run_id"],
                "cutoff": session_payload["forecast_cutoff"],
                "session_date": session_date,
                "session_region": region,
                "input_fingerprint": authoritative_row.get("request_fingerprint"),
                "expected_episode_count": len(call_row["episode_ids"]),
                "observed_episode_provider_row_count": len(call_row["episode_ids"]),
                "raw_validated_attention_row_count": len(scientific_rows),
                "raw_claimed_provider_value": raw_claimed_provider_value,
                "normalized_result_reference": path_ref(artifacts["normalized"]),
                "raw_evidence_references": raw_evidence_references_for_call(call_row["authoritative_run_id"], authoritative_row, artifacts),
                "repair_retry_lineage": call_level_row["repair_retry_lineage"],
            }
        )

        mapped_episode_count = 0
        for episode_id in call_row["episode_ids"]:
            parent = parent_by_episode.get(episode_id)
            episode_meta = episode_rows_by_id.get(episode_id)
            if parent is None or episode_meta is None:
                missing_mapping_rows.append({"call_id": call_id, "episode_id": episode_id, "reason": "EPISODE_METADATA_MISSING"})
                continue
            if parent["source_session_id"] != source_session_id:
                duplicate_conflicts.append({"conflict_type": "EPISODE_SESSION_CONFLICT", "episode_id": episode_id, "call_id": call_id})
                continue
            ep_key = episode_provider_key(episode_id, provider)
            if ep_key in episode_provider_keys:
                duplicate_conflicts.append({"conflict_type": "EPISODE_PROVIDER_DUPLICATE", "key": ep_key, "call_id": call_id})
                continue
            episode_provider_keys.add(ep_key)
            member_event_ids = list(parent.get("member_event_ids") or episode_meta.get("member_event_ids") or [])
            member_indicator_names = list(episode_meta.get("member_indicator_names") or [])
            relevant_scientific_rows: list[dict[str, Any]] = []
            resolved_event_ids: set[str] = set()
            fallback_name_resolutions: list[dict[str, Any]] = []
            for event_id in member_event_ids:
                scientific_row = scientific_by_event_id.get(str(event_id))
                if scientific_row is None:
                    continue
                if sha256_row(scientific_row) != sha256_row(scientific_row):
                    scientific_mutation_count += 1
                relevant_scientific_rows.append(scientific_row)
                resolved_event_ids.add(str(event_id))
            unresolved_member_event_ids = [str(event_id) for event_id in member_event_ids if str(event_id) not in resolved_event_ids]
            unresolved_indicator_names = []
            for indicator_name in member_indicator_names:
                session_event_id = session_event_id_by_name.get(indicator_name)
                if session_event_id is None or session_event_id in resolved_event_ids:
                    continue
                scientific_row = scientific_by_event_id.get(session_event_id)
                if scientific_row is None:
                    unresolved_indicator_names.append(indicator_name)
                    continue
                relevant_scientific_rows.append(scientific_row)
                resolved_event_ids.add(session_event_id)
                fallback_name_resolutions.append(
                    {
                        "indicator_name": indicator_name,
                        "resolved_scientific_event_id": session_event_id,
                    }
                )
            episode_mapping_resolution = "DIRECT_EVENT_ID_OR_EXACT_INDICATOR_NAME"
            if not relevant_scientific_rows:
                relevant_scientific_rows = list(scientific_rows)
                episode_mapping_resolution = "AUTHORITATIVE_EPISODE_MAP_FULL_CALL_RESULT"
            if member_indicator_names and not fallback_name_resolutions and unresolved_member_event_ids and not resolved_event_ids:
                episode_mapping_resolution = "AUTHORITATIVE_EPISODE_MAP_FULL_CALL_RESULT"
            mapped_episode_count += 1
            episode_ids_seen.add(episode_id)
            provider_episode_counts[provider] += 1
            episode_provider_row = {
                "episode_id": episode_id,
                "source_session_id": source_session_id,
                "provider": provider,
                "model": model,
                "call_id": call_id,
                "attention_request_identity": authoritative_row.get("request_fingerprint"),
                "attention_selection_state": [row.get("attention_label") for row in relevant_scientific_rows],
                "canonical_row_status": [row.get("status", authoritative_row.get("attention_result", {}).get("status")) for row in relevant_scientific_rows],
                "reasoning_or_rationale_fields": [row.get("attention_reason") for row in relevant_scientific_rows],
                "confidence_fields": [row.get("confidence") for row in relevant_scientific_rows],
                "cutoff_lineage": session_payload["forecast_cutoff"],
                "source_result_identity": call_row["authoritative_result_fingerprint"],
                "member_event_ids": member_event_ids,
                "member_indicator_names": member_indicator_names,
                "matched_scientific_event_ids": [row.get("event_id") for row in relevant_scientific_rows],
                "unmatched_declared_member_event_ids": unresolved_member_event_ids,
                "fallback_name_resolutions": fallback_name_resolutions,
                "episode_mapping_resolution": episode_mapping_resolution,
                "primary_event_id": episode_meta.get("primary_event_id"),
                "episode_family": episode_meta.get("episode_family"),
                "release_ts": episode_meta.get("release_ts"),
                "raw_claimed_provider_value": raw_claimed_provider_value,
                "scientific_rows": relevant_scientific_rows,
                "normalized_result_reference": path_ref(artifacts["normalized"]),
                "raw_evidence_references": raw_evidence_references_for_call(call_row["authoritative_run_id"], authoritative_row, artifacts),
                "repair_retry_lineage": call_level_row["repair_retry_lineage"],
            }
            episode_provider_population.append(episode_provider_row)
            call_to_episode_provider_map.append(
                {
                    "call_id": call_id,
                    "source_session_id": source_session_id,
                    "provider": provider,
                    "episode_id": episode_id,
                    "episode_provider_key": ep_key,
                    "member_event_ids": member_event_ids,
                    "matched_scientific_event_ids": [row.get("event_id") for row in relevant_scientific_rows],
                    "episode_mapping_resolution": episode_mapping_resolution,
                    "source_result_identity": call_row["authoritative_result_fingerprint"],
                }
            )
        session_provider_reconciliation.append(
            {
                "source_session_id": source_session_id,
                "provider": provider,
                "model": model,
                "call_id": call_id,
                "expected_episode_provider_rows": len(call_row["episode_ids"]),
                "observed_episode_provider_rows": mapped_episode_count,
                "raw_validated_attention_row_count": len(scientific_rows),
                "reconciliation_decision": "PASSED" if mapped_episode_count == len(call_row["episode_ids"]) else "FAILED",
            }
        )

    relevant_episode_ids = {episode_id for call_row in call_inventory for episode_id in call_row["episode_ids"]}
    episode_rows_by_key: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in episode_provider_population:
        episode_rows_by_key[row["episode_id"]].append(row)
    for episode_id in sorted(relevant_episode_ids):
        episode_meta = episode_rows_by_id.get(episode_id)
        if episode_meta is None:
            missing_mapping_rows.append({"episode_id": episode_id, "reason": "EPISODE_ROW_MISSING"})
            continue
        rows = episode_rows_by_key.get(episode_id, [])
        provider_ids = sorted(row["provider"] for row in rows)
        call_ids = sorted(row["call_id"] for row in rows)
        mapping_refs = sorted(episode_provider_key(row["episode_id"], row["provider"]) for row in rows)
        coverage_decision = "FULL_PROVIDER_COVERAGE" if provider_ids == ["Anthropic", "Gemini", "OpenAI"] else "COVERAGE_GAP_OR_CONFLICT"
        if coverage_decision != "FULL_PROVIDER_COVERAGE":
            missing_mapping_rows.append({"episode_id": episode_id, "reason": "PROVIDER_COVERAGE_GAP", "observed_providers": provider_ids})
        episode_coverage_population.append(
            {
                "episode_id": episode_id,
                "source_session_id": (parent_by_episode.get(episode_id) or {}).get("source_session_id"),
                "expected_provider_count": 3,
                "observed_provider_count": len(rows),
                "provider_identities": provider_ids,
                "call_ids": call_ids,
                "mapping_references": mapping_refs,
                "coverage_decision": coverage_decision,
                "member_event_ids": list((parent_by_episode.get(episode_id) or {}).get("member_event_ids") or episode_meta.get("member_event_ids") or []),
            }
        )
        episode_provider_reconciliation.append(
            {
                "episode_id": episode_id,
                "expected_provider_count": 3,
                "observed_provider_count": len(rows),
                "provider_identities": provider_ids,
                "reconciliation_decision": "PASSED" if len(rows) == 3 and provider_ids == ["Anthropic", "Gemini", "OpenAI"] else "FAILED",
            }
        )

    duplicate_mapping_count = len(duplicate_conflicts)
    unexpected_provider_count = sum(1 for row in episode_provider_population if row["provider"] not in {"Anthropic", "Gemini", "OpenAI"})
    if unexpected_provider_count:
        for row in episode_provider_population:
            if row["provider"] not in {"Anthropic", "Gemini", "OpenAI"}:
                unexpected_mapping_rows.append({"episode_id": row["episode_id"], "provider": row["provider"], "reason": "UNEXPECTED_PROVIDER"})

    call_counts_ok = all(row["expected_event_count"] == row["returned_event_count"] for row in authoritative_call_inventory)
    session_counts_ok = all(row["expected_episode_provider_rows"] == row["observed_episode_provider_rows"] for row in session_provider_reconciliation)
    episode_counts_ok = all(row["observed_provider_count"] == 3 for row in episode_coverage_population)
    provider_counts_ok = provider_episode_counts == Counter({"Anthropic": 413, "Gemini": 413, "OpenAI": 413})
    provider_model_counts_ok = provider_call_counts == Counter({
        "Anthropic|claude-haiku-4-5": 68,
        "Gemini|gemini-2.5-flash-lite": 68,
        "OpenAI|gpt-4o-mini-2024-07-18": 68,
    })

    cross_population = {
        "call_expected_event_count_equals_linked_episode_provider_rows": call_counts_ok,
        "session_provider_counts_reconcile_to_call_contents": session_counts_ok,
        "every_episode_has_exactly_three_provider_mappings": episode_counts_ok,
        "sum_call_level_event_mappings": sum(row["returned_event_count"] for row in authoritative_call_inventory),
        "sum_episode_provider_rows": len(episode_provider_population),
        "cross_population_reconciliation_result": "PASSED" if call_counts_ok and session_counts_ok and episode_counts_ok and len(episode_provider_population) == 1239 else "FAILED",
    }

    provider_model_summary = {
        "provider_counts": dict(sorted(provider_episode_counts.items())),
        "provider_model_call_counts": dict(sorted(provider_call_counts.items())),
    }
    session_summary = {
        "session_count": len(sessions_seen),
        "session_provider_row_count": len(session_provider_population),
        "sessions_represented": sorted(sessions_seen),
    }
    episode_summary = {
        "episode_count": len(episode_coverage_population),
        "episode_provider_mapping_count": len(episode_provider_population),
        "episodes_with_exactly_three_provider_mappings": sum(1 for row in episode_coverage_population if row["observed_provider_count"] == 3),
    }

    if (
        len(authoritative_call_inventory) != 204
        or len(call_id_keys) != 204
        or len(session_provider_population) != 204
        or len(session_provider_keys) != 204
        or len(episode_coverage_population) != 413
        or len(episode_provider_population) != 1239
        or len(episode_provider_keys) != 1239
        or not provider_counts_ok
        or not provider_model_counts_ok
        or len(sessions_seen) != 68
        or duplicate_mapping_count != 0
        or unexpected_provider_count != 0
        or lineage_conflict_count != 0
        or missing_mapping_rows
        or scientific_mutation_count != 0
        or cross_population["cross_population_reconciliation_result"] != "PASSED"
    ):
        consolidation_status = "ATTENTION_RESULT_CONSOLIDATION_INCOMPLETE"
    else:
        consolidation_status = "ATTENTION_RESULT_CONSOLIDATION_COMPLETE"

    lineage_decision = (
        "AUTHORITATIVE_LINEAGE_CONFLICTS_PRESENT" if lineage_conflict_count else
        "AUTHORITATIVE_LINEAGE_INCOMPLETE" if any(not row["all_known_run_identities"] for row in call_lineage_ledger) else
        "ALL_AUTHORITATIVE_CALL_LINEAGE_RESOLVED"
    )
    coverage_decision = (
        "EPISODE_PROVIDER_MAPPING_CONFLICTS_PRESENT" if duplicate_mapping_count else
        "EPISODE_PROVIDER_MAPPING_GAPS_PRESENT" if missing_mapping_rows or unexpected_provider_count else
        "FULL_413_EPISODE_1239_PROVIDER_MAPPING_COVERAGE"
    )
    scientific_integrity_decision = (
        "SCIENTIFIC_FIELD_MUTATION_DETECTED" if scientific_mutation_count else
        "SCIENTIFIC_FIELDS_PRESERVED_UNCHANGED"
    )
    next_phase_decision = (
        "READY_FOR_ATTENTION_TO_PACK_LINEAGE_BINDING"
        if consolidation_status == "ATTENTION_RESULT_CONSOLIDATION_COMPLETE"
        else "REPAIR_ATTENTION_CONSOLIDATION" if coverage_decision != "EPISODE_PROVIDER_MAPPING_CONFLICTS_PRESENT" and lineage_decision != "AUTHORITATIVE_LINEAGE_CONFLICTS_PRESENT"
        else "GOVERNANCE_REVIEW_REQUIRED"
    )

    write_json(
        run_dir / "run_manifest.json",
        {
            "plan_id": PLAN_ID,
            "governing_full_completion_id": FULL_COMPLETION_ID,
            "move": "ATTENTION_RESULT_CONSOLIDATION",
            "provider_calls_executed": 0,
            "google_writes_executed": 0,
            "pack_construction_executed": 0,
            "forecast_execution_executed": 0,
            "outcome_attachment_executed": 0,
            "matrix_updates_executed": 0,
            "start_head": start_head,
        },
    )
    write_json(
        run_dir / "governing_artifact_manifest.json",
        {
            "plan_id": PLAN_ID,
            "governing_full_completion_id": FULL_COMPLETION_ID,
            "authoritative_call_inventory_source": path_ref(EXECUTION_OUTPUT_ROOT / FULL_COMPLETION_ID / "call_completion_reconciliation.jsonl"),
            "authoritative_batch_inventory_source": path_ref(EXECUTION_OUTPUT_ROOT / FULL_COMPLETION_ID / "authoritative_batch_result_inventory.jsonl"),
        },
    )
    write_json(
        run_dir / "consolidation_contract.json",
        {
            "canonical_object": "session_attention_map",
            "call_level_key": "call_id",
            "session_provider_key": "source_session_id + canonical provider",
            "episode_provider_key": "episode_id + canonical provider",
            "episode_level_key": "episode_id",
            "authoritative_selection_rule": "use governing full completion reconciliation only",
            "scientific_values_mutated": False,
            "provider_calls_executed": 0,
            "google_writes_executed": 0,
        },
    )
    write_jsonl(run_dir / "authoritative_call_inventory.jsonl", authoritative_call_inventory)
    write_jsonl(run_dir / "call_lineage_ledger.jsonl", call_lineage_ledger)
    write_jsonl(run_dir / "session_provider_population.jsonl", session_provider_population)
    write_jsonl(run_dir / "episode_provider_population.jsonl", episode_provider_population)
    write_jsonl(run_dir / "episode_coverage_population.jsonl", episode_coverage_population)
    write_jsonl(run_dir / "call_to_episode_provider_map.jsonl", call_to_episode_provider_map)
    write_jsonl(run_dir / "session_provider_reconciliation.jsonl", session_provider_reconciliation)
    write_jsonl(run_dir / "episode_provider_reconciliation.jsonl", episode_provider_reconciliation)
    write_json(run_dir / "cross_population_reconciliation.json", cross_population)
    write_json(run_dir / "provider_model_summary.json", provider_model_summary)
    write_json(run_dir / "session_summary.json", session_summary)
    write_json(run_dir / "episode_summary.json", episode_summary)
    write_jsonl(run_dir / "duplicate_conflict_ledger.jsonl", duplicate_conflicts)
    write_jsonl(run_dir / "missing_mapping_ledger.jsonl", missing_mapping_rows)
    write_jsonl(run_dir / "unexpected_mapping_ledger.jsonl", unexpected_mapping_rows)

    consolidation_summary = {
        "authoritative_call_level_row_count": len(authoritative_call_inventory),
        "unique_call_id_count": len(call_id_keys),
        "session_provider_row_count": len(session_provider_population),
        "unique_session_provider_key_count": len(session_provider_keys),
        "episode_count": len(episode_coverage_population),
        "episode_provider_mapping_count": len(episode_provider_population),
        "unique_episode_provider_key_count": len(episode_provider_keys),
        "provider_counts": dict(sorted(provider_episode_counts.items())),
        "provider_model_call_counts": dict(sorted(provider_call_counts.items())),
        "session_count": len(sessions_seen),
        "episodes_with_exactly_three_provider_mappings": episode_summary["episodes_with_exactly_three_provider_mappings"],
        "episodes_with_missing_provider_mappings": sum(1 for row in episode_coverage_population if row["observed_provider_count"] != 3),
        "duplicate_mapping_count": duplicate_mapping_count,
        "unexpected_provider_count": unexpected_provider_count,
        "authoritative_lineage_conflict_count": lineage_conflict_count,
        "blocked_runs_counted_as_authoritative": 0,
        "repaired_or_retried_calls_double_counted": 0,
        "unresolved_call_lineage_count": sum(1 for row in call_lineage_ledger if not row["all_known_run_identities"]),
        "scientific_field_mutation_count": scientific_mutation_count,
        "cross_population_reconciliation_result": cross_population["cross_population_reconciliation_result"],
    }
    write_json(run_dir / "consolidation_summary.json", consolidation_summary)
    write_json(
        run_dir / "consolidation_decision.json",
        {
            "consolidation_status": consolidation_status,
            "lineage_decision": lineage_decision,
            "coverage_decision": coverage_decision,
            "scientific_integrity_decision": scientific_integrity_decision,
            "next_phase_decision": next_phase_decision,
        },
    )

    return {
        "run_dir": run_dir,
        "summary": consolidation_summary,
        "decision": read_json(run_dir / "consolidation_decision.json"),
        "cross_population": cross_population,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, default=CONSOLIDATION_OUTPUT_ROOT)
    parser.add_argument("--fixed-timestamp")
    args = parser.parse_args(argv)
    result = execute_consolidation(output_root=args.output_root, fixed_timestamp=args.fixed_timestamp)
    print(
        json.dumps(
            {
                "run_dir": str(result["run_dir"]),
                "consolidation_status": result["decision"]["consolidation_status"],
                "authoritative_call_level_row_count": result["summary"]["authoritative_call_level_row_count"],
                "episode_provider_mapping_count": result["summary"]["episode_provider_mapping_count"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
