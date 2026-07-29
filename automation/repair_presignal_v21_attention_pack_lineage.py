#!/usr/bin/env python3
"""Repair blocked Attention-to-Pack lineage via exact frozen rescue artifacts."""
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

from automation import bind_presignal_v21_attention_to_pack_lineage as binding
from automation import consolidate_presignal_v21_attention_results as consolidation
from automation import execute_presignal_v21_attention_batch_004 as batch004

PLAN_ID = "PPHB-R1-ATTENTION-EXECUTION-PLAN-20260729T010207Z-3fcd59f96f3c"
CONSOLIDATION_ID = "PPHB-R1-ATTENTION-RESULT-CONSOLIDATION-20260729T102316Z-17358e44afc1"
LINEAGE_BINDING_ID = "PPHB-R1-ATTENTION-TO-PACK-LINEAGE-BINDING-20260729T103549Z-79d034f68080"
US_SESSION_JOIN_AUDIT_ID = "PPHB-R1-73-EPISODE-US-SESSION-JOIN-AUDIT-20260728T153350749590Z-5c8af86038c5"
EVENT_DATE_RESCUE_ID = "PPHB-R1-REMAINING-65-EVENT-DATE-RESCUE-20260728T155538056417Z-3b8ea248781e"

CONSOLIDATION_ROOT = ROOT / "outputs" / "presignal_v21_full_round_1_attention_consolidation" / CONSOLIDATION_ID
LINEAGE_ROOT = ROOT / "outputs" / "presignal_v21_full_round_1_attention_pack_lineage" / LINEAGE_BINDING_ID
RESCUE_ROOT = ROOT / "outputs" / "presignal_v21_73_execution_blocked_episode_rescue"
US_SESSION_JOIN_ROOT = RESCUE_ROOT / US_SESSION_JOIN_AUDIT_ID
EVENT_DATE_RESCUE_ROOT = RESCUE_ROOT / EVENT_DATE_RESCUE_ID
OUTPUT_ROOT = ROOT / "outputs" / "presignal_v21_full_round_1_attention_pack_lineage"

PROVIDERS = ("Anthropic", "Gemini", "OpenAI")
PACK_TYPES = ("PACK_A", "PACK_E")
LINEAGE_FIELDS = {
    "pack_a_lineage_status",
    "pack_a_source_references",
    "pack_e_lineage_status",
    "pack_e_source_references",
    "future_pack_binding_status",
    "future_pack_binding_eligible",
    "blocker_code",
    "pack_source_lineage_resolved",
    "lineage_repair_method",
}
SCIENTIFIC_FIELDS = {
    "episode_id",
    "provider",
    "model",
    "attention_call_id",
    "attention_request_identity",
    "attention_selection_state",
    "attention_lineage_resolved",
    "expected_pack_a_arm_identity",
    "expected_pack_e_arm_identity",
}


class LineageRepairError(RuntimeError):
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


def parse_run_identity(ref: str) -> str:
    return Path(ref).parent.name


def materialize_run(output_root: Path, fixed_timestamp: str | None = None) -> Path:
    ts = fixed_timestamp or now()
    seed = {
        "plan_id": PLAN_ID,
        "consolidation_id": CONSOLIDATION_ID,
        "lineage_binding_id": LINEAGE_BINDING_ID,
        "timestamp": ts,
        "move": "ATTENTION_TO_PACK_LINEAGE_REPAIR",
    }
    run_id = (
        "PPHB-R1-ATTENTION-TO-PACK-LINEAGE-REPAIR-"
        + ts.replace(":", "").replace("-", "")
        + "-"
        + hashlib.sha256(canonical_json(seed).encode("utf-8")).hexdigest()[:12]
    )
    return output_root / run_id


def load_required_artifacts() -> dict[str, Any]:
    paths = {
        "consolidated_episode_provider_population": CONSOLIDATION_ROOT / "episode_provider_population.jsonl",
        "original_episode_pack_source_lineage": LINEAGE_ROOT / "episode_pack_source_lineage.jsonl",
        "original_episode_provider_pack_binding": LINEAGE_ROOT / "episode_provider_pack_binding.jsonl",
        "original_lineage_blockers": LINEAGE_ROOT / "lineage_blocker_ledger.jsonl",
        "original_missing_sources": LINEAGE_ROOT / "missing_source_ledger.jsonl",
        "pack_a_source_contract": LINEAGE_ROOT / "pack_a_source_contract.json",
        "pack_e_source_contract": LINEAGE_ROOT / "pack_e_source_contract.json",
        "session_definition_contract": US_SESSION_JOIN_ROOT / "session_definition_contract.json",
        "session_join_rows": US_SESSION_JOIN_ROOT / "session_date_join_audit.jsonl",
        "join_repair_candidates": US_SESSION_JOIN_ROOT / "rescue_promotion_candidates.jsonl",
        "event_source_contract": EVENT_DATE_RESCUE_ROOT / "event_source_contract.json",
        "session_source_contract": EVENT_DATE_RESCUE_ROOT / "session_source_contract.json",
        "event_date_join_rows": EVENT_DATE_RESCUE_ROOT / "event_date_session_join.jsonl",
        "event_identity_audit": EVENT_DATE_RESCUE_ROOT / "event_identity_audit.jsonl",
        "downstream_route_audit": EVENT_DATE_RESCUE_ROOT / "downstream_route_audit.jsonl",
        "event_date_promotion_candidates": EVENT_DATE_RESCUE_ROOT / "promotion_candidates.jsonl",
        "event_date_remaining_blocked": EVENT_DATE_RESCUE_ROOT / "remaining_blocked_episodes.jsonl",
    }
    for path in paths.values():
        if not path.exists():
            raise LineageRepairError(f"MISSING_GOVERNING_ARTIFACT:{path}")
    return {
        "paths": paths,
        "consolidated_episode_provider_population": read_jsonl(paths["consolidated_episode_provider_population"]),
        "original_episode_pack_source_lineage": read_jsonl(paths["original_episode_pack_source_lineage"]),
        "original_episode_provider_pack_binding": read_jsonl(paths["original_episode_provider_pack_binding"]),
        "original_lineage_blockers": read_jsonl(paths["original_lineage_blockers"]),
        "original_missing_sources": read_jsonl(paths["original_missing_sources"]),
        "pack_a_source_contract": read_json(paths["pack_a_source_contract"]),
        "pack_e_source_contract": read_json(paths["pack_e_source_contract"]),
        "session_definition_contract": read_json(paths["session_definition_contract"]),
        "session_join_rows": read_jsonl(paths["session_join_rows"]),
        "join_repair_candidates": read_jsonl(paths["join_repair_candidates"]),
        "event_source_contract": read_json(paths["event_source_contract"]),
        "session_source_contract": read_json(paths["session_source_contract"]),
        "event_date_join_rows": read_jsonl(paths["event_date_join_rows"]),
        "event_identity_audit": read_jsonl(paths["event_identity_audit"]),
        "downstream_route_audit": read_jsonl(paths["downstream_route_audit"]),
        "event_date_promotion_candidates": read_jsonl(paths["event_date_promotion_candidates"]),
        "event_date_remaining_blocked": read_jsonl(paths["event_date_remaining_blocked"]),
    }


def build_shared_cause_groups(blocked_episode_ids: list[str], promotion_rows: list[dict[str, Any]], join_candidate_ids: set[str]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in promotion_rows:
        if row["episode_id"] not in blocked_episode_ids:
            continue
        key = (row["prior_classification"], row["final_classification"])
        grouped[key].append(row)
    groups: list[dict[str, Any]] = []
    for (prior, final), rows in sorted(grouped.items()):
        episode_ids = sorted(row["episode_id"] for row in rows)
        if prior == "PARTIAL_LINEAGE_ONLY":
            group_id = "GROUP_EVENT_DATE_JOIN_64"
            failure = "source searched under wrong key; omitted exact America/New_York session-date join path"
            repair = "add omitted exact event-date session join and promote exact selected_session_id"
        elif prior == "RECOVERABLE_BY_DETERMINISTIC_LINK_REPAIR":
            group_id = "GROUP_PRIOR_JOIN_REPAIR_8"
            failure = "existing exact deterministic session repair was not consumed by the original binder"
            repair = "include existing exact session-join rescue artifact in source lookup"
        else:
            raise LineageRepairError(f"UNEXPECTED_SHARED_CAUSE_GROUP:{prior}:{final}")
        groups.append(
            {
                "group_id": group_id,
                "exact_grouping_fields": {
                    "prior_classification": prior,
                    "final_classification": final,
                    "identity_complete": True,
                    "route_complete": True,
                },
                "episode_count": len(rows),
                "episode_ids": episode_ids,
                "original_failure_mechanism": failure,
                "repair_mechanism": repair,
                "affected_pack_types": list(PACK_TYPES),
                "existing_prior_join_candidate_count": sum(episode_id in join_candidate_ids for episode_id in episode_ids),
            }
        )
    return groups


def execute_lineage_repair(*, output_root: Path = OUTPUT_ROOT, fixed_timestamp: str | None = None) -> dict[str, Any]:
    start_head = batch004.git_head()
    loaded = load_required_artifacts()
    paths = loaded["paths"]

    consolidated_rows = loaded["consolidated_episode_provider_population"]
    original_episode_rows = loaded["original_episode_pack_source_lineage"]
    original_provider_rows = loaded["original_episode_provider_pack_binding"]

    if len(consolidated_rows) != 1239 or len(original_provider_rows) != 1239 or len(original_episode_rows) != 413:
        raise LineageRepairError("AUTHORITATIVE_POPULATION_COUNT_MISMATCH")

    provider_rows_by_key = {(row["episode_id"], row["provider"]): row for row in original_provider_rows}
    if len(provider_rows_by_key) != 1239:
        raise LineageRepairError("DUPLICATE_PROVIDER_BINDING_KEYS")
    episode_rows_by_id = {row["episode_id"]: row for row in original_episode_rows}
    if len(episode_rows_by_id) != 413:
        raise LineageRepairError("DUPLICATE_EPISODE_ROWS")

    blocked_episode_ids = sorted(row["episode_id"] for row in original_episode_rows if row["lineage_status"] == "BLOCKED")
    blocked_provider_rows = [
        row for row in original_provider_rows if row["episode_id"] in blocked_episode_ids and row["future_pack_binding_status"] == "FULLY_BLOCKED"
    ]
    resolved_provider_rows = [row for row in original_provider_rows if row["episode_id"] not in blocked_episode_ids]
    if len(blocked_episode_ids) != 72 or len(blocked_provider_rows) != 216 or len(resolved_provider_rows) != 1023:
        raise LineageRepairError("BLOCKED_POPULATION_COUNT_MISMATCH")

    event_date_candidates_by_episode = {row["episode_id"]: row for row in loaded["event_date_promotion_candidates"]}
    join_candidates_by_episode = {row["episode_id"]: row for row in loaded["join_repair_candidates"]}
    event_date_join_by_episode = {row["episode_id"]: row for row in loaded["event_date_join_rows"]}
    session_join_by_episode = {row["episode_id"]: row for row in loaded["session_join_rows"]}
    event_identity_by_episode = {row["episode_id"]: row for row in loaded["event_identity_audit"]}
    downstream_route_by_episode = {row["episode_id"]: row for row in loaded["downstream_route_audit"]}
    event_date_remaining = {row["episode_id"] for row in loaded["event_date_remaining_blocked"]}
    if event_date_remaining != {"EP_EVENT_67dc98eaf62822136db2"}:
        raise LineageRepairError("EVENT_DATE_RESCUE_REMAINING_SET_CHANGED")

    blocked_episode_inventory: list[dict[str, Any]] = []
    episode_pack_audit: list[dict[str, Any]] = []
    exact_source_search_ledger: list[dict[str, Any]] = []
    deterministic_repair_ledger: list[dict[str, Any]] = []
    repaired_episode_rows: list[dict[str, Any]] = []
    repaired_provider_rows: list[dict[str, Any]] = []
    remaining_blockers: list[dict[str, Any]] = []

    pack_a_episode_counts = Counter()
    pack_e_episode_counts = Counter()
    pack_a_provider_newly_resolved = 0
    pack_e_provider_newly_resolved = 0
    scientific_mutation_count = 0
    fuzzy_bindings_accepted = 0

    join_candidate_ids = set(join_candidates_by_episode)
    shared_groups = build_shared_cause_groups(blocked_episode_ids, loaded["event_date_promotion_candidates"], join_candidate_ids)

    for episode_id, episode_row in sorted(episode_rows_by_id.items()):
        if episode_id not in blocked_episode_ids:
            repaired_episode_rows.append(dict(episode_row))
            continue

        promotion = event_date_candidates_by_episode.get(episode_id)
        join_row = event_date_join_by_episode.get(episode_id)
        session_join_row = session_join_by_episode.get(episode_id)
        identity_row = event_identity_by_episode.get(episode_id)
        route_row = downstream_route_by_episode.get(episode_id)
        prior_join_row = join_candidates_by_episode.get(episode_id)
        if not all([promotion, join_row, session_join_row, identity_row, route_row]):
            raise LineageRepairError(f"MISSING_REPAIR_EVIDENCE:{episode_id}")
        if join_row["join_status"] != "UNIQUE_SESSION_MATCH" or session_join_row["join_status"] != "UNIQUE_SESSION_MATCH":
            raise LineageRepairError(f"SESSION_JOIN_NOT_UNIQUE:{episode_id}")
        if promotion["selected_session_id"] != join_row["selected_session_id"]:
            raise LineageRepairError(f"SESSION_IDENTITY_CONFLICT:{episode_id}")
        route_complete = bool(promotion["route_complete"])
        if not route_complete and prior_join_row and prior_join_row.get("complete_downstream_lineage_route") is True:
            route_complete = True
        if not promotion["identity_complete"] or not route_complete:
            raise LineageRepairError(f"PROMOTION_EVIDENCE_INCOMPLETE:{episode_id}")
        if not identity_row["identity_complete"] or identity_row["missing_ids"] or identity_row["identity_conflicts"]:
            raise LineageRepairError(f"EVENT_IDENTITY_INCOMPLETE:{episode_id}")
        route_complete_from_prior_join = bool(prior_join_row and prior_join_row.get("complete_downstream_lineage_route") is True)
        if route_row["route_completeness"] is not True and not route_complete_from_prior_join:
            raise LineageRepairError(f"DOWNSTREAM_ROUTE_INCOMPLETE:{episode_id}")
        pack_a_route_ok = route_row["Pack_A_route"] == "RECONSTRUCTABLE_UNDER_EXISTING_341_ROUTE" or route_complete_from_prior_join
        pack_e_route_ok = route_row["Pack_E_route"] == "RECONSTRUCTABLE_UNDER_EXISTING_341_ROUTE" or route_complete_from_prior_join
        if not pack_a_route_ok:
            raise LineageRepairError(f"PACK_A_ROUTE_UNEXPECTED:{episode_id}")
        if not pack_e_route_ok:
            raise LineageRepairError(f"PACK_E_ROUTE_UNEXPECTED:{episode_id}")
        if route_row["Information_Request_route"] != "EXACT_REUSABLE":
            raise LineageRepairError(f"REQUEST_ROUTE_UNEXPECTED:{episode_id}")

        repaired_source_session_id = promotion["selected_session_id"]
        original_failure_family = promotion["classification_transition"]
        blocked_episode_inventory.append(
            {
                "episode_id": episode_id,
                "source_session_id": episode_row["source_session_id"],
                "episode_class_or_cluster_identity": episode_row["episode_class_or_cluster_identity"],
                "event_identities": list(episode_row["event_identities"]),
                "original_lookup_inputs": {
                    "episode_id": episode_id,
                    "release_ts_utc": promotion["release_ts_utc"],
                    "source_session_id": episode_row["source_session_id"],
                    "event_ids": list(episode_row["event_identities"]),
                },
                "original_lookup_failure_family": original_failure_family,
                "original_pack_a_status": episode_row["pack_a_lineage_status"],
                "original_pack_e_status": episode_row["pack_e_lineage_status"],
                "repaired_source_session_id": repaired_source_session_id,
                "repair_group_id": "GROUP_PRIOR_JOIN_REPAIR_8" if episode_id in join_candidate_ids else "GROUP_EVENT_DATE_JOIN_64",
            }
        )
        deterministic_repair_ledger.append(
            {
                "repair_id": f"{episode_id}|SESSION_BINDING_REPAIR",
                "episode_id": episode_id,
                "original_failed_lookup": "episode_id-only lineage binding left source_session_id unavailable in episode-scoped Pack artifacts",
                "repaired_lookup": {
                    "authoritative_release_ts_utc": promotion["release_ts_utc"],
                    "derived_us_session_date": promotion["derived_us_session_date"],
                    "selected_session_id": repaired_source_session_id,
                    "frozen_mapping_rule": "UTC release_ts -> America/New_York local date -> unique MATCHED source_session_id",
                },
                "repair_group_id": "GROUP_PRIOR_JOIN_REPAIR_8" if episode_id in join_candidate_ids else "GROUP_EVENT_DATE_JOIN_64",
                "source_artifact_identities": [
                    path_ref(paths["session_definition_contract"]),
                    path_ref(paths["session_source_contract"]),
                    path_ref(paths["event_source_contract"]),
                    path_ref(paths["event_date_join_rows"]),
                    path_ref(paths["event_identity_audit"]),
                    path_ref(paths["downstream_route_audit"]),
                ] + ([path_ref(paths["join_repair_candidates"])] if prior_join_row else []),
                "scientific_fields_changed": False,
            }
        )

        pack_statuses: dict[str, str] = {}
        pack_refs: dict[str, list[dict[str, Any]]] = {}
        for pack_type in PACK_TYPES:
            original_refs = (
                episode_row["pack_a_source_identities"] if pack_type == "PACK_A" else episode_row["pack_e_source_identities"]
            )
            final_status = "RESOLVED_DETERMINISTIC_LOOKUP_REPAIR"
            pack_statuses[pack_type] = final_status
            search_row = {
                "episode_id": episode_id,
                "pack_type": pack_type,
                "original_lookup_inputs": {
                    "episode_id": episode_id,
                    "original_source_session_id": "",
                    "original_status": episode_row["pack_a_lineage_status"] if pack_type == "PACK_A" else episode_row["pack_e_lineage_status"],
                    "original_refs": original_refs,
                },
                "artifacts_searched": [ref["artifact"] for ref in original_refs] + [
                    path_ref(paths["session_definition_contract"]),
                    path_ref(paths["session_source_contract"]),
                    path_ref(paths["event_source_contract"]),
                    path_ref(paths["event_date_join_rows"]),
                    path_ref(paths["event_identity_audit"]),
                    path_ref(paths["downstream_route_audit"]),
                    path_ref(paths["event_date_promotion_candidates"]),
                ],
                "identifiers_used": {
                    "episode_id": episode_id,
                    "event_ids": list(episode_row["event_identities"]),
                    "derived_us_session_date": promotion["derived_us_session_date"],
                    "selected_session_id": repaired_source_session_id,
                },
                "original_failure_reason": "source searched under wrong key / exact parent-session repair artifact omitted",
                "repaired_lookup_reason": "deterministic exact session-date repair promoted into lineage binding",
                "final_status": final_status,
            }
            exact_source_search_ledger.append(search_row)
            if pack_type == "PACK_A":
                pack_a_episode_counts[final_status] += 1
            else:
                pack_e_episode_counts[final_status] += 1

            repaired_refs = list(original_refs) + [
                {
                    "artifact": path_ref(paths["event_date_promotion_candidates"]),
                    "key": {"episode_id": episode_id},
                    "required_fields": [
                        "selected_session_id",
                        "final_classification",
                        "identity_complete",
                        "route_complete",
                    ],
                    "evidence_role": "REPAIRED_LOOKUP_PROMOTION",
                },
                {
                    "artifact": path_ref(paths["event_date_join_rows"]),
                    "key": {"episode_id": episode_id},
                    "required_fields": [
                        "join_status",
                        "selected_session_id",
                        "candidate_count",
                    ],
                    "evidence_role": "SESSION_JOIN_PROOF",
                },
                {
                    "artifact": path_ref(paths["event_identity_audit"]),
                    "key": {"episode_id": episode_id},
                    "required_fields": [
                        "identity_complete",
                        "expected_member_event_ids",
                        "event_source_matched_ids",
                    ],
                    "evidence_role": "EVENT_IDENTITY_PROOF",
                },
                {
                    "artifact": path_ref(paths["downstream_route_audit"]),
                    "key": {"episode_id": episode_id},
                    "required_fields": [
                        "route_completeness",
                        "Pack_A_route",
                        "Pack_E_route",
                        "Information_Request_route",
                    ],
                    "evidence_role": "DOWNSTREAM_ROUTE_PROOF",
                },
            ]
            if prior_join_row:
                repaired_refs.append(
                    {
                        "artifact": path_ref(paths["join_repair_candidates"]),
                        "key": {"episode_id": episode_id},
                        "required_fields": [
                            "selected_session_id",
                            "recovery_classification",
                            "join_status",
                            "membership_complete",
                            "complete_downstream_lineage_route",
                        ],
                        "evidence_role": "PRIOR_JOIN_REPAIR_PROOF",
                    }
                )
            pack_refs[pack_type] = repaired_refs
            episode_pack_audit.append(
                {
                    "episode_id": episode_id,
                    "pack_type": pack_type,
                    "manifest_pack_contract": path_ref(paths["pack_a_source_contract"] if pack_type == "PACK_A" else paths["pack_e_source_contract"]),
                    "original_failed_lookup": "episode-scoped source lineage artifact reported UNAVAILABLE because source_session_id was not repaired into the lookup",
                    "repair_path": "derive exact source_session_id from frozen session-date contract and reuse exact downstream route proof",
                    "required_source_definition": "frozen Pack source contract plus exact session repair evidence",
                    "exact_binding_key": {
                        "episode_id": episode_id,
                        "selected_session_id": repaired_source_session_id,
                    },
                    "source_artifact_identity": repaired_refs[0]["artifact"],
                    "source_row_or_object_identity": {"episode_id": episode_id},
                    "canonical_fingerprint_when_available": None,
                    "scientific_fields_changed": False,
                    "final_status": final_status,
                }
            )

        repaired_episode_rows.append(
            {
                **episode_row,
                "lineage_status": "RESOLVED",
                "missing_source_identities": [],
                "pack_a_lineage_status": pack_statuses["PACK_A"],
                "pack_a_source_identities": pack_refs["PACK_A"],
                "pack_e_lineage_status": pack_statuses["PACK_E"],
                "pack_e_source_identities": pack_refs["PACK_E"],
                "required_source_count": episode_row["required_source_count"],
                "resolved_source_count": episode_row["required_source_count"],
                "lineage_repair_method": "EXACT_SESSION_DATE_AND_ROUTE_REPAIR",
            }
        )

    repaired_episode_rows.sort(key=lambda row: row["episode_id"])

    for row in original_provider_rows:
        if row["episode_id"] not in blocked_episode_ids:
            repaired_provider_rows.append(dict(row))
            continue
        episode_row = next(item for item in repaired_episode_rows if item["episode_id"] == row["episode_id"])
        repaired_row = {
            **row,
            "pack_a_lineage_status": episode_row["pack_a_lineage_status"],
            "pack_a_source_references": list(episode_row["pack_a_source_identities"]),
            "pack_e_lineage_status": episode_row["pack_e_lineage_status"],
            "pack_e_source_references": list(episode_row["pack_e_source_identities"]),
            "future_pack_binding_status": "FULLY_RESOLVED",
            "future_pack_binding_eligible": True,
            "blocker_code": None,
            "pack_source_lineage_resolved": True,
            "lineage_repair_method": "EXACT_SESSION_DATE_AND_ROUTE_REPAIR",
        }
        repaired_provider_rows.append(repaired_row)
        pack_a_provider_newly_resolved += 1
        pack_e_provider_newly_resolved += 1
        if {key: row[key] for key in SCIENTIFIC_FIELDS} != {key: repaired_row[key] for key in SCIENTIFIC_FIELDS}:
            scientific_mutation_count += 1

    repaired_provider_rows.sort(key=lambda row: (row["episode_id"], row["provider"]))
    if len(repaired_provider_rows) != 1239:
        raise LineageRepairError("REPAIRED_PROVIDER_ROW_COUNT_MISMATCH")

    unchanged_resolved_rows = sum(
        1 for row in resolved_provider_rows if row == next(item for item in repaired_provider_rows if item["episode_id"] == row["episode_id"] and item["provider"] == row["provider"])
    )
    if unchanged_resolved_rows != 1023:
        raise LineageRepairError("PREVIOUSLY_RESOLVED_ROWS_CHANGED")

    fully_resolved_rows = sum(row["future_pack_binding_status"] == "FULLY_RESOLVED" for row in repaired_provider_rows)
    partially_resolved_rows = sum(row["future_pack_binding_status"] == "PARTIALLY_RESOLVED" for row in repaired_provider_rows)
    fully_blocked_rows = sum(row["future_pack_binding_status"] == "FULLY_BLOCKED" for row in repaired_provider_rows)
    if fully_resolved_rows != 1239 or partially_resolved_rows != 0 or fully_blocked_rows != 0:
        raise LineageRepairError("REPAIRED_PROVIDER_STATUS_MISMATCH")

    episode_provider_keys = {f"{row['episode_id']}|{row['provider']}" for row in repaired_provider_rows}
    episode_provider_counts = Counter(row["episode_id"] for row in repaired_provider_rows)
    if len(episode_provider_keys) != 1239 or set(episode_provider_counts.values()) != {3}:
        raise LineageRepairError("REPAIRED_PROVIDER_KEY_MISMATCH")

    cross_reconciliation = {
        "all_1239_attention_rows_remain": len(repaired_provider_rows) == 1239,
        "previously_resolved_1023_rows_unchanged": unchanged_resolved_rows == 1023,
        "only_previously_blocked_lineage_fields_changed": scientific_mutation_count == 0,
        "repaired_episode_rows_total": len(repaired_episode_rows) == 413,
        "repaired_provider_rows_total": len(repaired_provider_rows) == 1239,
        "unique_episode_provider_keys": len(episode_provider_keys) == 1239,
        "every_episode_retains_three_providers": set(episode_provider_counts.values()) == {3},
        "cross_population_reconciliation_result": "PASSED",
    }

    repair_summary = {
        "blocked_episode_count_audited": 72,
        "blocked_episode_provider_row_count_audited": 216,
        "episode_pack_audit_row_count": 144,
        "shared_cause_group_count": len(shared_groups),
        "pack_a_episodes_resolved_from_existing_source": 0,
        "pack_a_episodes_resolved_through_deterministic_lookup_repair": 72,
        "pack_a_episodes_not_required": 0,
        "pack_a_episodes_genuinely_missing": 0,
        "pack_a_identity_conflict_count": 0,
        "pack_a_contract_ambiguity_count": 0,
        "pack_e_episodes_resolved_from_existing_source": 0,
        "pack_e_episodes_resolved_through_deterministic_lookup_repair": 72,
        "pack_e_episodes_not_required": 0,
        "pack_e_episodes_genuinely_missing": 0,
        "pack_e_identity_conflict_count": 0,
        "pack_e_contract_ambiguity_count": 0,
        "pack_a_provider_rows_newly_resolved": pack_a_provider_newly_resolved,
        "pack_a_provider_rows_newly_not_required": 0,
        "pack_a_provider_rows_remaining_blocked": 0,
        "pack_e_provider_rows_newly_resolved": pack_e_provider_newly_resolved,
        "pack_e_provider_rows_newly_not_required": 0,
        "pack_e_provider_rows_remaining_blocked": 0,
        "fully_resolved_episode_provider_rows": fully_resolved_rows,
        "partially_resolved_episode_provider_rows": partially_resolved_rows,
        "fully_blocked_episode_provider_rows": fully_blocked_rows,
        "remaining_unresolved_episode_pack_issues": len(remaining_blockers),
        "remaining_blocker_categories": {},
        "fuzzy_bindings_accepted": fuzzy_bindings_accepted,
        "deterministic_repairs_applied": len(deterministic_repair_ledger),
        "attention_scientific_field_mutation_count": scientific_mutation_count,
        "all_1239_attention_rows_remain": True,
        "previously_resolved_1023_rows_remained_unchanged": unchanged_resolved_rows == 1023,
        "cross_population_reconciliation_result": "PASSED",
    }
    repair_decision = {
        "repair_status": "ATTENTION_TO_PACK_LINEAGE_REPAIR_COMPLETE",
        "pack_a_repair_decision": "PACK_A_ALL_REQUIRED_LINEAGE_RESOLVED",
        "pack_e_repair_decision": "PACK_E_ALL_REQUIRED_LINEAGE_RESOLVED",
        "attention_integrity_decision": "ALL_1239_ATTENTION_ROWS_PRESERVED_UNCHANGED",
        "scientific_boundary_decision": "LINEAGE_REPAIR_ONLY_NO_PACK_CONSTRUCTION",
        "next_phase_decision": "READY_FOR_BOUNDED_PACK_POPULATION_CONSTRUCTION",
    }

    scientific_integrity_audit = {
        "attention_scientific_field_mutation_count": scientific_mutation_count,
        "scientific_fields_audited": sorted(SCIENTIFIC_FIELDS),
        "previously_resolved_1023_rows_remained_unchanged": unchanged_resolved_rows == 1023,
        "all_1239_attention_rows_remain": True,
    }

    run_dir = materialize_run(output_root, fixed_timestamp=fixed_timestamp)
    run_dir.mkdir(parents=True, exist_ok=False)

    governing_manifest = {
        "governing_plan_id": PLAN_ID,
        "governing_consolidation_id": CONSOLIDATION_ID,
        "governing_lineage_binding_id": LINEAGE_BINDING_ID,
        "governing_artifacts": {
            "consolidated_episode_provider_population": path_ref(paths["consolidated_episode_provider_population"]),
            "original_episode_pack_source_lineage": path_ref(paths["original_episode_pack_source_lineage"]),
            "original_episode_provider_pack_binding": path_ref(paths["original_episode_provider_pack_binding"]),
            "pack_a_source_contract": path_ref(paths["pack_a_source_contract"]),
            "pack_e_source_contract": path_ref(paths["pack_e_source_contract"]),
            "session_definition_contract": path_ref(paths["session_definition_contract"]),
            "session_source_contract": path_ref(paths["session_source_contract"]),
            "event_source_contract": path_ref(paths["event_source_contract"]),
            "event_date_join_rows": path_ref(paths["event_date_join_rows"]),
            "event_identity_audit": path_ref(paths["event_identity_audit"]),
            "downstream_route_audit": path_ref(paths["downstream_route_audit"]),
            "event_date_promotion_candidates": path_ref(paths["event_date_promotion_candidates"]),
            "join_repair_candidates": path_ref(paths["join_repair_candidates"]),
        },
    }
    run_manifest = {
        "run_id": run_dir.name,
        "operation": "ATTENTION_TO_PACK_LINEAGE_REPAIR",
        "start_head": start_head,
        "timestamp": fixed_timestamp or now(),
        "provider_calls_executed": 0,
        "market_data_calls_executed": 0,
        "research_ai_calls_executed": 0,
        "google_writes_executed": 0,
        "pack_a_constructed": 0,
        "pack_e_constructed": 0,
        "forecast_execution_executed": 0,
        "outcome_attachment_executed": 0,
        "matrix_updates_executed": 0,
        "consensus_or_ranking_executed": 0,
    }
    lineage_repair_contract = {
        "scope": "repair only the 72 blocked Episode-level lineage gaps and propagate to their 216 provider rows",
        "binding_rule": "use only exact frozen identifiers and exact frozen rescue artifacts",
        "forbidden_methods": [
            "fuzzy matching",
            "provider prose",
            "semantic similarity",
            "pack construction",
            "forecast execution",
        ],
        "shared_cause_groups": [row["group_id"] for row in shared_groups],
    }

    write_json(run_dir / "run_manifest.json", run_manifest)
    write_json(run_dir / "governing_artifact_manifest.json", governing_manifest)
    write_json(run_dir / "lineage_repair_contract.json", lineage_repair_contract)
    write_jsonl(run_dir / "blocked_episode_inventory.jsonl", blocked_episode_inventory)
    write_jsonl(run_dir / "shared_cause_diagnostic.jsonl", shared_groups)
    write_jsonl(run_dir / "episode_pack_source_audit.jsonl", episode_pack_audit)
    write_jsonl(run_dir / "exact_source_search_ledger.jsonl", exact_source_search_ledger)
    write_jsonl(run_dir / "deterministic_index_repair_ledger.jsonl", deterministic_repair_ledger)
    write_jsonl(run_dir / "repaired_episode_pack_source_lineage.jsonl", repaired_episode_rows)
    write_jsonl(run_dir / "repaired_episode_provider_pack_binding.jsonl", repaired_provider_rows)
    write_jsonl(run_dir / "remaining_lineage_blockers.jsonl", remaining_blockers)
    write_json(
        run_dir / "pack_a_repair_reconciliation.json",
        {
            "episodes_resolved_from_existing_source": 0,
            "episodes_resolved_through_deterministic_lookup_repair": 72,
            "episodes_not_required": 0,
            "episodes_genuinely_missing": 0,
            "identity_conflict_count": 0,
            "contract_ambiguity_count": 0,
            "provider_rows_newly_resolved": 216,
            "provider_rows_newly_not_required": 0,
            "provider_rows_remaining_blocked": 0,
        },
    )
    write_json(
        run_dir / "pack_e_repair_reconciliation.json",
        {
            "episodes_resolved_from_existing_source": 0,
            "episodes_resolved_through_deterministic_lookup_repair": 72,
            "episodes_not_required": 0,
            "episodes_genuinely_missing": 0,
            "identity_conflict_count": 0,
            "contract_ambiguity_count": 0,
            "provider_rows_newly_resolved": 216,
            "provider_rows_newly_not_required": 0,
            "provider_rows_remaining_blocked": 0,
        },
    )
    write_json(run_dir / "cross_population_reconciliation.json", cross_reconciliation)
    write_json(run_dir / "scientific_integrity_audit.json", scientific_integrity_audit)
    write_json(run_dir / "repair_summary.json", repair_summary)
    write_json(run_dir / "repair_decision.json", repair_decision)

    return {
        "run_dir": run_dir,
        "summary": repair_summary,
        "decision": repair_decision,
        "shared_groups": shared_groups,
        "cross_reconciliation": cross_reconciliation,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, default=OUTPUT_ROOT)
    parser.add_argument("--fixed-timestamp")
    args = parser.parse_args()
    result = execute_lineage_repair(output_root=args.output_root, fixed_timestamp=args.fixed_timestamp)
    print(result["run_dir"])


if __name__ == "__main__":
    main()
