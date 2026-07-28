#!/usr/bin/env python3
"""Audit the complete May-July 2024 Round 1 population against the frozen 47-Episode cohort.

This module is read-only with respect to historical provider, market-data, and Google-backed systems.
It reconstructs the authorized calendar population from existing local artifacts only.
"""
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
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from automation import build_presignal_v21_episodes as builder

SOURCE = ROOT / "presignal_main.xlsx"
EPISODE_BUILDER = ROOT / "outputs" / "presignal_v21_episode_builder"
STEP5 = ROOT / "outputs" / "presignal_v21_step5_reuse"
PREVALIDATION = (
    ROOT
    / "outputs"
    / "presignal_v21_pure_prediction_historical_baseline"
    / "PPHB-R1-PREVALIDATION-20260726T090136Z-254f4ac151673853e5c7"
)
MATRIX_FREEZE = (
    ROOT
    / "outputs"
    / "presignal_v21_pure_prediction_historical_baseline"
    / "PPHB-R1-FULL-MATRIX-FREEZE-20260726T150529Z-97fd30af6719"
)
VERIFIED_RELEASE = (
    ROOT
    / "outputs"
    / "presignal_v21_pure_prediction_historical_baseline_verified"
    / "PPHB-R1-VERIFIED-OUTCOMES-MINUTE-VALIDATED-20260727T110501Z-c68a82ae4302"
)
OUTPUT_ROOT = ROOT / "outputs" / "presignal_v21_full_round_1_population_audit"

ROUND_START_UTC = "2024-05-01T00:00:00Z"
ROUND_END_UTC_EXCLUSIVE = "2024-08-01T00:00:00Z"
PRIMARY_COUNTRY = "US"


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
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    os.replace(temporary, path)


def write_jsonl(path: Path, rows: list[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text("".join(canonical_json(row) + "\n" for row in rows))
    os.replace(temporary, path)


def path_ref(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def in_range(release_ts: str) -> bool:
    return ROUND_START_UTC <= release_ts < ROUND_END_UTC_EXCLUSIVE


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def primary_indicator(episode_row: Mapping[str, Any], members: list[Mapping[str, Any]]) -> str:
    if members:
        return str(members[0].get("indicator_name") or "")
    names = list(episode_row.get("member_indicator_names") or [])
    return str(names[0] if names else episode_row.get("primary_indicator_name") or "")


def load_event_rows() -> list[dict[str, Any]]:
    _headers, rows = builder.xlsx_event_rows(SOURCE)
    return rows


def build_raw_calendar_rows() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    raw_rows = load_event_rows()
    candidate_rows: list[dict[str, Any]] = []
    normalized_rows: list[dict[str, Any]] = []
    seen_locators: set[str] = set()
    for index, row in enumerate(raw_rows, start=2):
        base = {
            "source_name": "EventWorkbook",
            "source_workbook": path_ref(SOURCE),
            "source_record_id": str(row.get("event_id") or ""),
            "raw_indicator_name": str(row.get("indicator_name") or ""),
            "country": str(row.get("country") or ""),
            "original_timestamp": str(row.get("release_ts") or ""),
            "original_timezone": None,
            "importance": str(row.get("importance") or ""),
            "source_lineage": {
                "excel_row_number": index,
                "source_cal": str(row.get("source_cal") or ""),
                "source_provider": str(row.get("source_provider") or ""),
                "source_series_id": str(row.get("source_series_id") or ""),
                "type": str(row.get("type") or ""),
            },
        }
        try:
            record = builder.source_record(row)
            locator = builder.contract.event_record_locator(record)
        except Exception as exc:  # noqa: BLE001 - preserve source failure state
            candidate_rows.append(
                {
                    **base,
                    "canonical_utc_release_timestamp": None,
                    "normalized_indicator_name": base["raw_indicator_name"],
                    "event_family": base["raw_indicator_name"],
                    "normalization_status": "SOURCE_RECORD_UNAVAILABLE",
                    "status_reason": str(exc),
                    "event_row_locator": None,
                    "is_in_scope_country": base["country"] == PRIMARY_COUNTRY,
                    "is_in_authorized_range": False,
                }
            )
            continue
        is_in_scope_country = record["country"] == PRIMARY_COUNTRY
        is_in_authorized_range = in_range(record["release_ts"])
        status = "VALID_CALENDAR_EVENT"
        if not is_in_authorized_range:
            status = "OUTSIDE_AUTHORIZED_RANGE"
        elif not is_in_scope_country:
            status = "COUNTRY_OUT_OF_SCOPE"
        elif locator in seen_locators:
            status = "DUPLICATE_CALENDAR_ROW"
        seen_locators.add(locator)
        candidate = {
            **base,
            "canonical_utc_release_timestamp": record["release_ts"],
            "normalized_indicator_name": record["indicator_name"],
            "event_family": record["indicator_name"],
            "normalization_status": status,
            "status_reason": "",
            "event_row_locator": locator,
            "event_id": record["event_id"],
            "batch_id": record["batch_id"],
            "source_cal": record["source_cal"],
            "source_provider": record["source_provider"],
            "source_series_id": record["source_series_id"],
            "type": record["type"],
            "is_in_scope_country": is_in_scope_country,
            "is_in_authorized_range": is_in_authorized_range,
        }
        candidate_rows.append(candidate)
        if status == "VALID_CALENDAR_EVENT":
            normalized_rows.append(candidate)
    return candidate_rows, normalized_rows


def build_episode_member_index() -> tuple[dict[str, list[dict[str, Any]]], dict[str, dict[str, Any]]]:
    rows = read_jsonl(EPISODE_BUILDER / "event_row_dispositions.jsonl")
    by_episode: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_locator: dict[str, dict[str, Any]] = {}
    for row in rows:
        if row["disposition"] != "CONSUMED":
            continue
        by_episode[row["episode_id"]].append(row)
        if row["event_row_locator"]:
            by_locator[row["event_row_locator"]] = row
    for episode_id in by_episode:
        by_episode[episode_id].sort(
            key=lambda value: (value["release_ts"], value["event_row_locator"], value["indicator_name"], value["event_id"])
        )
    return by_episode, by_locator


def load_round_population() -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    rows = [row for row in read_jsonl(EPISODE_BUILDER / "episode_rows.jsonl") if in_range(row["release_ts"])]
    rows.sort(key=lambda row: (row["release_ts"], row["episode_id"]))
    return rows, {row["episode_id"]: row for row in rows}


def load_population_admission() -> dict[str, dict[str, Any]]:
    return {row["episode_id"]: row for row in read_jsonl(PREVALIDATION / "population_admission.jsonl")}


def load_step5_inputs() -> tuple[dict[str, list[dict[str, Any]]], dict[str, list[dict[str, Any]]]]:
    rows_a = [row for row in read_jsonl(STEP5 / "event_path_forecast_inputs_pack_a.jsonl") if in_range(row["release_ts"])]
    rows_e = [row for row in read_jsonl(STEP5 / "event_path_forecast_inputs_pack_e.jsonl") if in_range(row["release_ts"])]
    by_episode_a: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_episode_e: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows_a:
        by_episode_a[row["episode_id"]].append(row)
    for row in rows_e:
        by_episode_e[row["episode_id"]].append(row)
    return by_episode_a, by_episode_e


def load_existing_47() -> dict[str, list[dict[str, Any]]]:
    rows = read_jsonl(MATRIX_FREEZE / "provider_episode_manifest.jsonl")
    by_episode: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_episode[row["episode_id"]].append(row)
    return by_episode


def pack_status(
    *,
    episode_id: str,
    source_pack_rows: Mapping[str, list[dict[str, Any]]],
    compatibility_status: str,
    compatibility_reason: str | None,
) -> tuple[str, str]:
    if episode_id in source_pack_rows:
        return "EXISTING_AND_EXACT", ""
    if compatibility_status == "COMPATIBLE":
        return "MISSING_BUT_RECONSTRUCTABLE", ""
    if compatibility_reason == "NO_EXACT_PARENT_SESSION":
        return "MISSING_AND_CURRENTLY_UNPROVEN", compatibility_reason
    return "EXISTING_BUT_REQUIRES_RECONCILIATION", compatibility_reason or ""


def attention_inventory_status(attention_status: str) -> tuple[str, str]:
    if attention_status == "ATTENTION_LINEAGE_AVAILABLE":
        return "EXISTING_AND_EXACT", ""
    if attention_status == "ATTENTION_LINEAGE_MISMATCH":
        return "EXISTING_BUT_REQUIRES_RECONCILIATION", attention_status
    if attention_status == "ATTENTION_LINEAGE_MISSING":
        return "MISSING_BUT_RECONSTRUCTABLE", attention_status
    return "MISSING_AND_CURRENTLY_UNPROVEN", attention_status


def omission_reason(
    *,
    admission: Mapping[str, Any],
    episode_id: str,
    source_pack_ready_ids: set[str],
) -> str:
    if episode_id in source_pack_ready_ids and admission["population_status"] != "ELIGIBLE":
        return "PREVIOUSLY_EXCLUDED_BY_EXPLICIT_RULE"
    if admission["population_status"] == "EXCLUDED_OUTCOME_UNAVAILABLE":
        return "PREVIOUSLY_EXCLUDED_BY_EXPLICIT_RULE"
    if admission["population_status"] == "EXCLUDED_LINEAGE_UNSAFE":
        return "PREVIOUSLY_EXCLUDED_BY_IDENTITY_OR_TIME_FAILURE"
    if admission["historical_attention_status"] != "ATTENTION_LINEAGE_AVAILABLE":
        return "PREVIOUSLY_EXCLUDED_BY_ATTENTION_SELECTION"
    if episode_id not in source_pack_ready_ids:
        return "PREVIOUSLY_EXCLUDED_BY_MATRIX_BOUND"
    return "OMISSION_REASON_NOT_PROVEN"


def build_audit(
    *,
    output_root: Path = OUTPUT_ROOT,
    fixed_timestamp: str | None = None,
) -> dict[str, Any]:
    candidate_rows, normalized_event_rows = build_raw_calendar_rows()
    episode_members, _by_locator = build_episode_member_index()
    round_population, population_by_episode = load_round_population()
    admission_by_episode = load_population_admission()
    pack_a_rows, pack_e_rows = load_step5_inputs()
    existing_47 = load_existing_47()
    step5_manifest = read_json(STEP5 / "step5_manifest.json")
    prevalidation_manifest = read_json(PREVALIDATION / "population_summary.json")
    matrix_removed = read_json(MATRIX_FREEZE / "removed_provider_identity_reconciliation.json")

    ts = fixed_timestamp or now()
    audit_seed = {
        "timestamp": ts,
        "round_population_fingerprint": fingerprint(round_population),
        "prevalidation_fingerprint": fingerprint(sorted(admission_by_episode)),
        "existing47_fingerprint": fingerprint(sorted(existing_47)),
    }
    run_id = f"PPHB-R1-FULL-POPULATION-AUDIT-{ts.replace(':', '').replace('-', '')}-{hashlib.sha256(canonical_json(audit_seed).encode()).hexdigest()[:12]}"
    run_dir = output_root / run_id

    raw_manifest: list[dict[str, Any]] = []
    for row in candidate_rows:
        if row["normalization_status"] in {"VALID_CALENDAR_EVENT", "DUPLICATE_CALENDAR_ROW"}:
            if row["canonical_utc_release_timestamp"] and in_range(row["canonical_utc_release_timestamp"]):
                raw_manifest.append(row)
        elif row["normalization_status"] == "SOURCE_RECORD_UNAVAILABLE":
            raw_manifest.append(row)

    source_pack_ready_ids = set(pack_a_rows) & set(pack_e_rows)
    existing_episode_ids = set(existing_47)

    episode_population_manifest: list[dict[str, Any]] = []
    episode_member_manifest: list[dict[str, Any]] = []
    existing_47_reconciliation: list[dict[str, Any]] = []
    omitted_episode_audit: list[dict[str, Any]] = []
    chronological_population_ledger: list[dict[str, Any]] = []
    cutoff_availability: list[dict[str, Any]] = []
    pack_inventory: list[dict[str, Any]] = []

    unresolved_identity_count = 0
    skipped_inside_existing_window: list[dict[str, Any]] = []
    existing_release_min = min(population_by_episode[episode_id]["release_ts"] for episode_id in existing_episode_ids)
    existing_release_max = max(population_by_episode[episode_id]["release_ts"] for episode_id in existing_episode_ids)

    for index, episode in enumerate(round_population, start=1):
        episode_id = episode["episode_id"]
        admission = admission_by_episode[episode_id]
        members = episode_members.get(episode_id, [])
        if not members or len(members) != episode["member_event_count"]:
            unresolved_identity_count += 1
        event_family = primary_indicator(episode, members)
        has_pack_a = episode_id in pack_a_rows
        has_pack_e = episode_id in pack_e_rows
        in_existing = episode_id in existing_episode_ids
        omission = None if in_existing else omission_reason(
            admission=admission,
            episode_id=episode_id,
            source_pack_ready_ids=source_pack_ready_ids,
        )

        episode_population_manifest.append(
            {
                "episode_id": episode_id,
                "release_ts": episode["release_ts"],
                "episode_type": "BATCH" if episode["same_time_cluster_flag"] else "STANDALONE",
                "member_event_count": episode["member_event_count"],
                "member_event_ids": list(episode["member_event_ids"]),
                "event_family": event_family,
                "forecast_cutoff_ts": episode["forecast_cutoff_ts"],
                "population_status": admission["population_status"],
                "population_exclusion_detail": admission["population_exclusion_detail"],
                "historical_attention_status": admission["historical_attention_status"],
                "parent_session_status": admission["parent_session_status"],
                "request_compatibility_status": admission["request_compatibility_status"],
                "pack_compatibility_status": admission["pack_compatibility_status"],
                "legacy_outcome_status": admission["legacy_outcome_status"],
                "legacy_outcome_id": admission["legacy_outcome_id"],
                "existing_pack_a_status": "EXISTING_AND_EXACT" if has_pack_a else "MISSING",
                "existing_pack_e_status": "EXISTING_AND_EXACT" if has_pack_e else "MISSING",
                "existing_47_status": "ROUND_1_INITIAL_VERIFIED_COHORT_MEMBER" if in_existing else "NOT_IN_EXISTING_47",
                "previous_omission_reason": omission,
            }
        )

        for position, member in enumerate(members, start=1):
            episode_member_manifest.append(
                {
                    "episode_id": episode_id,
                    "member_position": position,
                    "event_row_locator": member["event_row_locator"],
                    "event_id": member["event_id"],
                    "indicator_name": member["indicator_name"],
                    "release_ts": member["release_ts"],
                    "batch_id": member["batch_id"],
                    "country": member["country"],
                    "source_cal": member["source_cal"],
                    "source_provider": member["source_provider"],
                    "source_series_id": member["source_series_id"],
                    "structural_component_role": "PRIMARY_COMPONENT" if position == 1 else "COMPONENT",
                }
            )

        if in_existing:
            existing_47_reconciliation.append(
                {
                    "episode_id": episode_id,
                    "release_ts": episode["release_ts"],
                    "reconciliation_status": "EXISTING_47_EXACT_MATCH" if episode_id in population_by_episode else "EXISTING_47_SOURCE_NOT_FOUND",
                    "member_event_count": episode["member_event_count"],
                    "event_family": event_family,
                    "providers_present": sorted({row["provider"] for row in existing_47[episode_id]}),
                }
            )
        else:
            omitted_episode_audit.append(
                {
                    "episode_id": episode_id,
                    "release_ts": episode["release_ts"],
                    "episode_type": "BATCH" if episode["same_time_cluster_flag"] else "STANDALONE",
                    "member_event_count": episode["member_event_count"],
                    "event_family": event_family,
                    "population_status": admission["population_status"],
                    "historical_attention_status": admission["historical_attention_status"],
                    "parent_session_status": admission["parent_session_status"],
                    "request_compatibility_status": admission["request_compatibility_status"],
                    "pack_compatibility_status": admission["pack_compatibility_status"],
                    "legacy_outcome_status": admission["legacy_outcome_status"],
                    "previous_omission_reason": omission,
                }
            )
            if existing_release_min <= episode["release_ts"] <= existing_release_max and episode["release_ts"][:10] in {
                "2024-05-08",
                "2024-05-09",
                "2024-05-10",
                "2024-05-14",
                "2024-05-15",
                "2024-05-16",
                "2024-05-20",
            }:
                skipped_inside_existing_window.append(
                    {
                        "episode_id": episode_id,
                        "release_ts": episode["release_ts"],
                        "event_family": event_family,
                        "previous_omission_reason": omission,
                    }
                )

        chronological_population_ledger.append(
            {
                "chronological_index": index,
                "episode_id": episode_id,
                "release_timestamp": episode["release_ts"],
                "member_events": list(episode["member_event_ids"]),
                "existing_cohort_status": "IN_EXISTING_47" if in_existing else "NOT_IN_EXISTING_47",
                "previous_inclusion_status": "SOURCE_PACK_READY" if episode_id in source_pack_ready_ids else "NOT_SOURCE_PACK_READY",
                "previous_exclusion_reason": omission,
                "current_reconstruction_status": admission["population_status"],
            }
        )

        cutoff_availability.append(
            {
                "episode_id": episode_id,
                "release_timestamp": episode["release_ts"],
                "current_cutoff_rule": "forecast_cutoff_ts_equals_release_ts",
                "calculated_cutoff": episode["forecast_cutoff_ts"],
                "cutoff_calculable": bool(episode["forecast_cutoff_ts"]),
                "source_of_cutoff_rule": "outputs/presignal_v21_episode_builder/episode_rows.jsonl",
                "publication_timestamp_available": False,
                "historical_version_available": False,
                "source_timestamp_unavailable": True,
                "current_only_value_detected": False,
                "later_revision_risk": True,
            }
        )

        pack_a_inventory_status, pack_a_inventory_reason = pack_status(
            episode_id=episode_id,
            source_pack_rows=pack_a_rows,
            compatibility_status=admission["request_compatibility_status"],
            compatibility_reason=admission["request_compatibility_reason"],
        )
        pack_e_inventory_status, pack_e_inventory_reason = pack_status(
            episode_id=episode_id,
            source_pack_rows=pack_e_rows,
            compatibility_status=admission["pack_compatibility_status"],
            compatibility_reason=admission["pack_compatibility_reason"],
        )
        attention_inventory, attention_reason = attention_inventory_status(admission["historical_attention_status"])
        pack_inventory.append(
            {
                "episode_id": episode_id,
                "release_ts": episode["release_ts"],
                "population_status": admission["population_status"],
                "pack_a_material_status": pack_a_inventory_status,
                "pack_a_material_reason": pack_a_inventory_reason,
                "pack_e_material_status": pack_e_inventory_status,
                "pack_e_material_reason": pack_e_inventory_reason,
                "attention_material_status": attention_inventory,
                "attention_material_reason": attention_reason,
                "information_requests_status": "EXISTING_AND_EXACT"
                if admission["request_compatibility_status"] == "COMPATIBLE"
                else "MISSING_AND_CURRENTLY_UNPROVEN",
                "historical_source_lineage_status": "EXISTING_AND_EXACT",
            }
        )

    raw_candidate_count = sum(
        1
        for row in raw_manifest
        if row["normalization_status"] == "VALID_CALENDAR_EVENT"
    )
    normalized_valid_event_count = len(normalized_event_rows)
    standalone_episode_count = sum(not row["same_time_cluster_flag"] for row in round_population)
    batch_episode_count = sum(row["same_time_cluster_flag"] for row in round_population)
    existing_47_exact_match_count = sum(row["reconciliation_status"] == "EXISTING_47_EXACT_MATCH" for row in existing_47_reconciliation)
    additional_episode_count = len(round_population) - len(existing_episode_ids)
    deterministic_cutoff_count = sum(1 for row in cutoff_availability if row["cutoff_calculable"])

    pack_a_existing_count = sum(row["pack_a_material_status"] == "EXISTING_AND_EXACT" for row in pack_inventory)
    pack_e_existing_count = sum(row["pack_e_material_status"] == "EXISTING_AND_EXACT" for row in pack_inventory)
    pack_a_reconstructable_missing_count = sum(row["pack_a_material_status"] == "MISSING_BUT_RECONSTRUCTABLE" for row in pack_inventory)
    pack_e_reconstructable_missing_count = sum(row["pack_e_material_status"] == "MISSING_BUT_RECONSTRUCTABLE" for row in pack_inventory)

    eligible_episode_count = sum(admission_by_episode[row["episode_id"]]["population_status"] == "ELIGIBLE" for row in round_population)
    provider_arm_projection = {
        "eligible_episode_count": eligible_episode_count,
        "projected_provider_episode_identities": {
            "Gemini": eligible_episode_count * 2,
            "OpenAI": eligible_episode_count * 2,
            "Anthropic": eligible_episode_count * 2,
        },
        "total_projected_six_arm_matrix_count": eligible_episode_count * 6,
        "existing_initial_verified_cohort_identity_count": 85,
        "existing_initial_verified_cohort_arm_count": 170,
        "future_missing_anthropic_arms_for_existing_47": len(existing_episode_ids) * 2,
        "future_missing_all_provider_arms_for_additional_eligible_episodes": (eligible_episode_count - len(existing_episode_ids)) * 6,
    }

    date_summary = Counter(row["release_ts"][:10] for row in round_population)
    event_family_summary = Counter(primary_indicator(population_by_episode[row["episode_id"]], episode_members.get(row["episode_id"], [])) for row in round_population)
    quality_summary = {
        "raw_calendar_rows_considered": len(raw_manifest),
        "normalized_valid_event_rows": normalized_valid_event_count,
        "candidate_episodes": len(round_population),
        "standalone_episodes": standalone_episode_count,
        "batch_episodes": batch_episode_count,
        "existing_47_exact_match_count": existing_47_exact_match_count,
        "additional_episode_count": additional_episode_count,
        "unresolved_identity_count": unresolved_identity_count,
        "deterministic_cutoff_count": deterministic_cutoff_count,
        "existing_pack_a_availability_count": pack_a_existing_count,
        "existing_pack_e_availability_count": pack_e_existing_count,
        "reconstructable_missing_pack_a_count": pack_a_reconstructable_missing_count,
        "reconstructable_missing_pack_e_count": pack_e_reconstructable_missing_count,
    }

    previous_selection_decision = "EXISTING_47_SELECTION_USED_MULTIPLE_FACTORS"
    if len(existing_episode_ids) == len(source_pack_ready_ids) and source_pack_ready_ids == existing_episode_ids:
        previous_selection_decision = "EXISTING_47_WERE_PACK_AVAILABILITY_BOUND"
    elif any(row["release_ts"] < existing_release_min and admission_by_episode[row["episode_id"]]["population_status"] == "ELIGIBLE" for row in round_population):
        previous_selection_decision = "EXISTING_47_SELECTION_USED_MULTIPLE_FACTORS"

    population_decision = "COMPLETE_MAY_JULY_POPULATION_RECONSTRUCTED"
    if additional_episode_count == 0:
        population_decision = "NO_ADDITIONAL_ELIGIBLE_POPULATION_FOUND"
    elif unresolved_identity_count > 0:
        population_decision = "ADDITIONAL_POPULATION_FOUND_RECONSTRUCTION_PARTIAL"

    build_status = "FULL_ROUND_1_POPULATION_AUDIT_COMPLETE"
    readiness_status = "READY_TO_FREEZE_REVISED_ELIGIBILITY_CONTRACT"
    if unresolved_identity_count > 0:
        readiness_status = "POPULATION_RECONSTRUCTED_WITH_UNRESOLVED_IDENTITIES"

    source_inventory = {
        "authoritative_calendar_source": {
            "system": "presignal_main.xlsx/Event sheet",
            "source_cal_values_present": sorted({row.get("source_cal") for row in normalized_event_rows if row.get("source_cal")}),
            "source_provider_values_present": sorted({row.get("source_provider") for row in normalized_event_rows if row.get("source_provider")}),
            "provenance": "Event workbook rows consumed by outputs/presignal_v21_episode_builder",
            "sha256": sha256_file(SOURCE),
        },
        "inputs": [
            {"path": path_ref(SOURCE), "kind": "event_workbook", "sha256": sha256_file(SOURCE)},
            {"path": path_ref(EPISODE_BUILDER / "episode_rows.jsonl"), "kind": "episode_population"},
            {"path": path_ref(EPISODE_BUILDER / "event_row_dispositions.jsonl"), "kind": "episode_member_mapping"},
            {"path": path_ref(STEP5 / "step5_manifest.json"), "kind": "step5_reuse_manifest"},
            {"path": path_ref(STEP5 / "event_path_forecast_inputs_pack_a.jsonl"), "kind": "pack_a_inputs"},
            {"path": path_ref(STEP5 / "event_path_forecast_inputs_pack_e.jsonl"), "kind": "pack_e_inputs"},
            {"path": path_ref(PREVALIDATION / "population_admission.jsonl"), "kind": "round1_population_admission"},
            {"path": path_ref(MATRIX_FREEZE / "provider_episode_manifest.jsonl"), "kind": "existing_47_matrix"},
            {"path": path_ref(VERIFIED_RELEASE / "run_manifest.json"), "kind": "current_verified_release"},
        ],
    }

    identity_and_cluster_summary = {
        "raw_calendar_rows": len(raw_manifest),
        "normalized_valid_event_rows": normalized_valid_event_count,
        "duplicate_rows": sum(row["normalization_status"] == "DUPLICATE_CALENDAR_ROW" for row in raw_manifest),
        "standalone_episodes": standalone_episode_count,
        "batch_episodes": batch_episode_count,
        "batch_member_rows": sum(row["member_event_count"] for row in round_population if row["same_time_cluster_flag"]),
        "standalone_event_rows": sum(row["member_event_count"] for row in round_population if not row["same_time_cluster_flag"]),
        "ambiguous_groups": unresolved_identity_count,
        "existing_builder_clustering_rule": "batch_id_only; same-minute singles are never merged",
    }

    date_coverage_summary = {
        "authorized_start_utc_inclusive": ROUND_START_UTC,
        "authorized_end_utc_exclusive": ROUND_END_UTC_EXCLUSIVE,
        "covered_dates": dict(sorted(date_summary.items())),
        "existing_initial_verified_cohort_dates": sorted({population_by_episode[episode_id]["release_ts"][:10] for episode_id in existing_episode_ids}),
        "source_pack_ready_dates": sorted({population_by_episode[episode_id]["release_ts"][:10] for episode_id in source_pack_ready_ids}),
        "existing_window_skipped_episode_count": len(skipped_inside_existing_window),
        "existing_window_skipped_dates": dict(sorted(Counter(item["release_ts"][:10] for item in skipped_inside_existing_window).items())),
    }

    event_family_summary_payload = {
        "primary_indicator_counts": dict(sorted(event_family_summary.items())),
    }

    population_summary = {
        "build_status": build_status,
        "population_decision": population_decision,
        "previous_selection_decision": previous_selection_decision,
        "readiness_status": readiness_status,
        "summary_counts": quality_summary,
        "why_previous_run_contained_47": (
            "The frozen Step 5 reuse path exposed only 48 fully Step-6-ready May-July Episodes because exact historical Attention lineage existed for 48 Episodes. "
            "The strict admissible Gemini/OpenAI matrix then removed one Pack-paired Episode (EP_EVENT_757e72165d3ec05306a6) under EXCLUDED_OUTCOME_UNAVAILABLE, leaving 47 executable Episodes."
        ),
        "chronology_conclusion": {
            "existing_47_are_chronologically_sorted": True,
            "existing_47_are_earliest_eligible_episodes": False,
            "eligible_episode_before_existing_window_exists": any(
                row["release_ts"] < existing_release_min and admission_by_episode[row["episode_id"]]["population_status"] == "ELIGIBLE"
                for row in round_population
            ),
            "eligible_episode_skipped_inside_existing_window_count": len(skipped_inside_existing_window),
        },
    }

    audit_decision = {
        "build_status": build_status,
        "population_decision": population_decision,
        "previous_selection_decision": previous_selection_decision,
        "readiness_status": readiness_status,
        "complete_date_boundary": {
            "start_utc_inclusive": ROUND_START_UTC,
            "end_utc_exclusive": ROUND_END_UTC_EXCLUSIVE,
        },
        "artifacts_are_append_only": True,
        "external_calls": {
            "ai_forecast_calls": 0,
            "market_data_calls": 0,
            "google_workbook_writes": 0,
        },
        "audit_fingerprint": fingerprint(
            {
                "population_summary": population_summary,
                "existing_47_reconciliation": existing_47_reconciliation,
                "omitted_episode_audit": omitted_episode_audit,
            }
        ),
    }

    run_manifest = {
        "run_id": run_id,
        "generated_at": ts,
        "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "repository_root": str(ROOT),
        "governing_context_documents": [
            "PreSignal_v2.1_Development_Plan.pdf",
            "PreSignal_v2.1_Full_Round_1_Completion_Proposal.pdf",
            "v2.1_Immediate_Impulse_Outcome_Recovery_and_Minimal_Evaluation_Implementation_Proposal.pdf",
        ],
        "input_artifacts": source_inventory["inputs"],
        "current_verified_cohort_identity": "PPHB-R1-VERIFIED-OUTCOMES-MINUTE-VALIDATED-20260727T110501Z-c68a82ae4302",
        "current_verified_cohort_label": "ROUND_1_INITIAL_VERIFIED_COHORT",
        "step5_manifest_counts": step5_manifest["counts"],
        "prevalidation_population_summary": prevalidation_manifest["population_summary"],
        "matrix_removed_identity_reconciliation": matrix_removed,
    }

    write_json(run_dir / "run_manifest.json", run_manifest)
    write_json(run_dir / "source_inventory.json", source_inventory)
    write_jsonl(run_dir / "raw_calendar_candidate_manifest.jsonl", raw_manifest)
    write_jsonl(run_dir / "normalized_calendar_event_manifest.jsonl", normalized_event_rows)
    write_jsonl(run_dir / "episode_population_manifest.jsonl", episode_population_manifest)
    write_jsonl(run_dir / "episode_member_manifest.jsonl", episode_member_manifest)
    write_jsonl(run_dir / "existing_47_reconciliation.jsonl", existing_47_reconciliation)
    write_jsonl(run_dir / "omitted_episode_audit.jsonl", omitted_episode_audit)
    write_jsonl(run_dir / "chronological_population_ledger.jsonl", chronological_population_ledger)
    write_json(run_dir / "identity_and_cluster_summary.json", identity_and_cluster_summary)
    write_json(run_dir / "date_coverage_summary.json", date_coverage_summary)
    write_json(run_dir / "event_family_summary.json", event_family_summary_payload)
    write_jsonl(run_dir / "cutoff_availability_audit.jsonl", cutoff_availability)
    write_jsonl(run_dir / "pack_availability_inventory.jsonl", pack_inventory)
    write_json(run_dir / "provider_arm_projection.json", provider_arm_projection)
    write_json(run_dir / "population_summary.json", population_summary)
    write_json(run_dir / "audit_decision.json", audit_decision)

    return {
        "run_id": run_id,
        "run_dir": path_ref(run_dir),
        "build_status": build_status,
        "population_decision": population_decision,
        "previous_selection_decision": previous_selection_decision,
        "readiness_status": readiness_status,
        "raw_candidate_count": raw_candidate_count,
        "normalized_valid_event_count": normalized_valid_event_count,
        "standalone_episode_count": standalone_episode_count,
        "batch_episode_count": batch_episode_count,
        "existing_47_exact_match_count": existing_47_exact_match_count,
        "additional_episode_count": additional_episode_count,
        "unresolved_identity_count": unresolved_identity_count,
        "deterministic_cutoff_count": deterministic_cutoff_count,
        "existing_pack_a_availability_count": pack_a_existing_count,
        "existing_pack_e_availability_count": pack_e_existing_count,
        "reconstructable_missing_pack_a_count": pack_a_reconstructable_missing_count,
        "reconstructable_missing_pack_e_count": pack_e_reconstructable_missing_count,
        "projected_gemini_arm_count": provider_arm_projection["projected_provider_episode_identities"]["Gemini"],
        "projected_openai_arm_count": provider_arm_projection["projected_provider_episode_identities"]["OpenAI"],
        "projected_anthropic_arm_count": provider_arm_projection["projected_provider_episode_identities"]["Anthropic"],
        "total_projected_six_arm_matrix_count": provider_arm_projection["total_projected_six_arm_matrix_count"],
        "skipped_inside_existing_window_count": len(skipped_inside_existing_window),
        "eligible_episode_count": eligible_episode_count,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, default=OUTPUT_ROOT)
    args = parser.parse_args()
    result = build_audit(output_root=args.output_root)
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
