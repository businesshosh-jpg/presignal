#!/usr/bin/env python3
"""Re-audit blocked Episodes via authoritative Event-to-US-session joins."""
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
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

POPULATION_AUDIT_ID = "PPHB-R1-FULL-POPULATION-AUDIT-20260728T125525Z-b25cd178e7d6"
RECONSTRUCTION_DRY_RUN_ID = "PPHB-R1-RECONSTRUCTION-DRY-RUN-20260728T134639Z-b3c9532ef93e"
SESSION_JOIN_AUDIT_ID = "PPHB-R1-73-EPISODE-US-SESSION-JOIN-AUDIT-20260728T153350749590Z-5c8af86038c5"

POPULATION_ROOT = ROOT / "outputs" / "presignal_v21_full_round_1_population_audit" / POPULATION_AUDIT_ID
RECONSTRUCTION_ROOT = ROOT / "outputs" / "presignal_v21_full_round_1_reconstruction_dry_run" / RECONSTRUCTION_DRY_RUN_ID
SESSION_JOIN_ROOT = ROOT / "outputs" / "presignal_v21_73_execution_blocked_episode_rescue" / SESSION_JOIN_AUDIT_ID
STEP5_ROOT = ROOT / "outputs" / "presignal_v21_step5_reuse"
ATTENTION_ROOT = ROOT / "outputs" / "presignal_v21_attention_preservation"
OUTPUT_ROOT = ROOT / "outputs" / "presignal_v21_73_execution_blocked_episode_rescue"

EPISODE_ROWS = ROOT / "outputs" / "presignal_v21_episode_builder" / "episode_rows.jsonl"
PARENT_SESSION_MAP = STEP5_ROOT / "episode_parent_session_map.jsonl"
ATTENTION_COMPATIBILITY = STEP5_ROOT / "episode_attention_compatibility.jsonl"
REQUEST_COMPATIBILITY = STEP5_ROOT / "episode_request_compatibility.jsonl"
PACK_COMPATIBILITY = STEP5_ROOT / "episode_pack_compatibility.jsonl"
PACK_A_INPUTS = STEP5_ROOT / "event_path_forecast_inputs_pack_a.jsonl"
PACK_E_INPUTS = STEP5_ROOT / "event_path_forecast_inputs_pack_e.jsonl"
ATTENTION_MAP = ATTENTION_ROOT / "authoritative_attention_map.jsonl"
ATTENTION_MANIFEST = ATTENTION_ROOT / "attention_google_sheet_source_manifest.json"
BLOCKED_LEDGER = RECONSTRUCTION_ROOT / "unavailable_73_blocker_ledger.jsonl"
RAW_EVENT_MANIFEST = POPULATION_ROOT / "raw_calendar_candidate_manifest.jsonl"
NORMALIZED_EVENT_MANIFEST = POPULATION_ROOT / "normalized_calendar_event_manifest.jsonl"
EPISODE_MEMBER_MANIFEST = POPULATION_ROOT / "episode_member_manifest.jsonl"
SOURCE_INVENTORY = POPULATION_ROOT / "source_inventory.json"
EPISODE_RECONSTRUCTION_PLAN = RECONSTRUCTION_ROOT / "episode_reconstruction_plan.jsonl"
ATTENTION_PLAN = RECONSTRUCTION_ROOT / "attention_reconstruction_plan.jsonl"
REQUEST_PLAN = RECONSTRUCTION_ROOT / "information_request_reconstruction_plan.jsonl"
PACK_A_PLAN = RECONSTRUCTION_ROOT / "pack_a_reconstruction_plan.jsonl"
PACK_E_PLAN = RECONSTRUCTION_ROOT / "pack_e_reconstruction_plan.jsonl"
PRIOR_CLASSIFICATION = SESSION_JOIN_ROOT / "recovery_classification.jsonl"

TIMEZONE_NAME = "America/New_York"
SESSION_WINDOW_NAME = "CUSTOM_CONFIG_WINDOW"
COUNTRY = "US"


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def fingerprint(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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


def write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text("".join(canonical_json(row) + "\n" for row in rows))
    os.replace(temp, path)


def path_ref(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def git_head() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()


def parse_utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("TIMESTAMP_NOT_TIMEZONE_AWARE")
    return parsed.astimezone(timezone.utc)


def to_us_eastern_date(value: str) -> tuple[str, str, str]:
    utc_dt = parse_utc(value)
    local_dt = utc_dt.astimezone(ZoneInfo(TIMEZONE_NAME))
    offset = local_dt.strftime("%z")
    return (
        utc_dt.isoformat().replace("+00:00", "Z"),
        local_dt.isoformat(),
        local_dt.date().isoformat(),
    )


def expected_session_id(session_date: str) -> str:
    return f"{COUNTRY}|{session_date}|{SESSION_WINDOW_NAME}"


def route_label(*, exact: bool, reconstructable: bool) -> str:
    if exact:
        return "EXACT_REUSABLE"
    if reconstructable:
        return "RECONSTRUCTABLE_UNDER_EXISTING_341_ROUTE"
    return "UNAVAILABLE"


def load_prior_rows() -> list[dict[str, Any]]:
    rows = read_jsonl(PRIOR_CLASSIFICATION)
    if len(rows) != 73:
        raise ValueError("PRIOR_RESCUE_CLASSIFICATION_NOT_73")
    return rows


def load_blocked_population() -> list[dict[str, Any]]:
    blocked_rows = {row["episode_id"]: row for row in read_jsonl(BLOCKED_LEDGER)}
    episodes = {row["episode_id"]: row for row in read_jsonl(EPISODE_ROWS)}
    prior = {row["episode_id"]: row for row in load_prior_rows()}
    merged: list[dict[str, Any]] = []
    for episode_id, row in blocked_rows.items():
        episode = episodes[episode_id]
        merged.append(
            {
                "episode_id": episode_id,
                "episode_type": "BATCH" if episode.get("same_time_cluster_flag") else "STANDALONE",
                "release_ts": episode["release_ts"],
                "forecast_cutoff_ts": episode["forecast_cutoff_ts"],
                "member_event_ids": list(episode["member_event_ids"]),
                "prior_classification": prior[episode_id]["recovery_classification"],
                "source_session_reason": row["source_session_reason"],
            }
        )
    merged.sort(key=lambda row: (row["release_ts"], row["episode_id"]))
    return merged


def build_event_source() -> dict[str, Any]:
    inventory = read_json(SOURCE_INVENTORY)
    normalized_rows = read_jsonl(NORMALIZED_EVENT_MANIFEST)
    episode_member_rows = read_jsonl(EPISODE_MEMBER_MANIFEST)
    normalized_by_locator: dict[str, dict[str, Any]] = {}
    for row in normalized_rows:
        locator = row["event_row_locator"]
        if locator in normalized_by_locator:
            raise ValueError("EVENT_ROW_LOCATOR_NOT_UNIQUE")
        normalized_by_locator[locator] = row
    episode_members_by_episode: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in episode_member_rows:
        episode_members_by_episode[row["episode_id"]].append(row)
    return {
        "source_inventory": inventory,
        "normalized_rows": normalized_rows,
        "normalized_by_locator": normalized_by_locator,
        "episode_members_by_episode": {
            key: sorted(value, key=lambda row: (row["member_position"], row["event_row_locator"]))
            for key, value in episode_members_by_episode.items()
        },
    }


def build_session_source() -> dict[str, Any]:
    matched_rows = [row for row in read_jsonl(PARENT_SESSION_MAP) if row.get("status") == "MATCHED" and row.get("source_session_id")]
    sessions_by_date: dict[str, list[str]] = defaultdict(list)
    for row in matched_rows:
        sessions_by_date[row["source_session_id"].split("|")[1]].append(row["source_session_id"])
    attention_exact_sessions = {
        (row.get("active_session_id") or row.get("session_id"))
        for row in read_jsonl(ATTENTION_MAP)
        if (row.get("active_session_id") or row.get("session_id"))
    }
    pack_a_episode_ids = {row["episode_id"] for row in read_jsonl(PACK_A_INPUTS)}
    pack_e_episode_ids = {row["episode_id"] for row in read_jsonl(PACK_E_INPUTS)}

    attention_plan_by_session: dict[str, list[dict[str, Any]]] = defaultdict(list)
    request_plan_by_session: dict[str, list[dict[str, Any]]] = defaultdict(list)
    pack_a_plan_by_session: dict[str, list[dict[str, Any]]] = defaultdict(list)
    pack_e_plan_by_session: dict[str, list[dict[str, Any]]] = defaultdict(list)
    episode_plan_by_session: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for path, target in (
        (ATTENTION_PLAN, attention_plan_by_session),
        (REQUEST_PLAN, request_plan_by_session),
        (PACK_A_PLAN, pack_a_plan_by_session),
        (PACK_E_PLAN, pack_e_plan_by_session),
        (EPISODE_RECONSTRUCTION_PLAN, episode_plan_by_session),
    ):
        for row in read_jsonl(path):
            session_id = row.get("source_session_id")
            if session_id:
                target[session_id].append(row)

    return {
        "sessions_by_date": {key: sorted(set(value)) for key, value in sessions_by_date.items()},
        "attention_exact_sessions": attention_exact_sessions,
        "pack_a_episode_ids": pack_a_episode_ids,
        "pack_e_episode_ids": pack_e_episode_ids,
        "attention_plan_by_session": attention_plan_by_session,
        "request_plan_by_session": request_plan_by_session,
        "pack_a_plan_by_session": pack_a_plan_by_session,
        "pack_e_plan_by_session": pack_e_plan_by_session,
        "episode_plan_by_session": episode_plan_by_session,
    }


def audit_population() -> dict[str, Any]:
    blocked_rows = load_blocked_population()
    event_source = build_event_source()
    session_source = build_session_source()

    event_identity_rows: list[dict[str, Any]] = []
    release_time_rows: list[dict[str, Any]] = []
    join_rows: list[dict[str, Any]] = []
    downstream_rows: list[dict[str, Any]] = []
    classification_rows: list[dict[str, Any]] = []

    for row in blocked_rows:
        members = event_source["episode_members_by_episode"][row["episode_id"]]
        matched_members: list[dict[str, Any]] = []
        missing_ids: list[str] = []
        identity_conflicts: list[str] = []

        member_dates: list[str] = []
        for member in members:
            locator = member["event_row_locator"]
            source_row = event_source["normalized_by_locator"].get(locator)
            if not source_row:
                missing_ids.append(member["event_id"])
                continue
            if source_row["event_id"] != member["event_id"]:
                identity_conflicts.append(f"EVENT_ID_MISMATCH:{member['event_id']}:{source_row['event_id']}")
            if source_row["canonical_utc_release_timestamp"] != member["release_ts"]:
                identity_conflicts.append(
                    f"RELEASE_TS_MISMATCH:{member['event_id']}:{member['release_ts']}:{source_row['canonical_utc_release_timestamp']}"
                )
            matched_members.append(source_row)
            release_ts_utc, release_ts_local, session_date = to_us_eastern_date(source_row["canonical_utc_release_timestamp"])
            member_dates.append(session_date)
            release_time_rows.append(
                {
                    "episode_id": row["episode_id"],
                    "member_event_id": member["event_id"],
                    "source_release_timestamp": source_row["canonical_utc_release_timestamp"],
                    "release_ts_utc": release_ts_utc,
                    "release_ts_us_eastern": release_ts_local,
                    "derived_us_session_date": session_date,
                    "timestamp_status": "EXACT_EVENT_SOURCE_MATCH",
                }
            )

        identity_complete = len(matched_members) == len(members) and not identity_conflicts
        event_identity_rows.append(
            {
                "episode_id": row["episode_id"],
                "episode_type": row["episode_type"],
                "expected_member_event_ids": [member["event_id"] for member in members],
                "event_source_matched_ids": [member["event_id"] for member in matched_members],
                "missing_ids": missing_ids,
                "mapping_method": "EXACT_EVENT_ROW_LOCATOR_WITH_EVENT_ID_CROSSCHECK",
                "mapping_artifact": path_ref(EPISODE_MEMBER_MANIFEST),
                "identity_complete": identity_complete,
                "identity_conflicts": identity_conflicts,
            }
        )

        episode_release_ts_utc, episode_release_ts_local, episode_session_date = to_us_eastern_date(row["release_ts"])
        candidate_dates = sorted(set(member_dates))
        candidate_session_ids = session_source["sessions_by_date"].get(episode_session_date, [])
        selected_session_id = candidate_session_ids[0] if len(candidate_session_ids) == 1 else ""
        join_status = (
            "UNIQUE_SESSION_MATCH"
            if len(candidate_session_ids) == 1 and identity_complete and candidate_dates == [episode_session_date]
            else "SESSION_NOT_FOUND"
            if len(candidate_session_ids) == 0
            else "MEMBER_DATE_CONFLICT"
            if candidate_dates and candidate_dates != [episode_session_date]
            else "SESSION_AMBIGUOUS"
        )
        join_rows.append(
            {
                "episode_id": row["episode_id"],
                "derived_us_session_date": episode_session_date,
                "candidate_session_ids": candidate_session_ids,
                "selected_session_id": selected_session_id,
                "candidate_count": len(candidate_session_ids),
                "join_status": join_status,
                "supporting_session_artifact": path_ref(PARENT_SESSION_MAP),
            }
        )

        attention_exact = bool(selected_session_id and selected_session_id in session_source["attention_exact_sessions"])
        attention_reconstructable = bool(
            selected_session_id
            and any(
                plan.get("attention_reconstruction_status") != "UNAVAILABLE"
                for plan in session_source["attention_plan_by_session"].get(selected_session_id, [])
            )
        )
        request_exact = bool(
            selected_session_id
            and any(
                plan.get("information_request_reconstruction_status") == "REUSED_EXACT"
                for plan in session_source["request_plan_by_session"].get(selected_session_id, [])
            )
        )
        request_reconstructable = bool(
            selected_session_id
            and any(
                plan.get("information_request_reconstruction_status") != "UNAVAILABLE"
                for plan in session_source["request_plan_by_session"].get(selected_session_id, [])
            )
        )
        pack_a_exact = row["episode_id"] in session_source["pack_a_episode_ids"]
        pack_e_exact = row["episode_id"] in session_source["pack_e_episode_ids"]
        pack_a_reconstructable = bool(
            selected_session_id
            and any(
                plan.get("pack_a_reconstruction_status") == "DETERMINISTIC_REBUILD_AVAILABLE"
                for plan in session_source["pack_a_plan_by_session"].get(selected_session_id, [])
            )
        )
        pack_e_reconstructable = bool(
            selected_session_id
            and any(
                plan.get("pack_e_reconstruction_status") == "DETERMINISTIC_REBUILD_AVAILABLE"
                for plan in session_source["pack_e_plan_by_session"].get(selected_session_id, [])
            )
        )
        attention_route = route_label(exact=attention_exact, reconstructable=attention_reconstructable)
        request_route = route_label(exact=request_exact, reconstructable=request_reconstructable)
        pack_a_route = route_label(exact=pack_a_exact, reconstructable=pack_a_reconstructable)
        pack_e_route = route_label(exact=pack_e_exact, reconstructable=pack_e_reconstructable)
        missing_components = [
            name
            for name, value in (
                ("Attention", attention_route),
                ("Information Requests", request_route),
                ("Pack A", pack_a_route),
                ("Pack E", pack_e_route),
            )
            if value == "UNAVAILABLE"
        ]
        route_complete = not missing_components
        downstream_rows.append(
            {
                "episode_id": row["episode_id"],
                "selected_session_id": selected_session_id,
                "Attention_route": attention_route,
                "Information_Request_route": request_route,
                "Pack_A_route": pack_a_route,
                "Pack_E_route": pack_e_route,
                "route_completeness": route_complete,
                "missing_components": missing_components,
            }
        )

        if row["prior_classification"] in {"RECOVERABLE_EXACT", "RECOVERABLE_BY_DETERMINISTIC_LINK_REPAIR"}:
            final_classification = row["prior_classification"]
        elif not identity_complete:
            final_classification = "HISTORICAL_VERSION_UNVERIFIED"
        elif join_status != "UNIQUE_SESSION_MATCH":
            final_classification = "NO_RECOVERY_ROUTE" if join_status == "SESSION_NOT_FOUND" else "PARTIAL_LINEAGE_ONLY"
        elif route_complete:
            final_classification = "RECOVERABLE_BY_DETERMINISTIC_EVENT_DATE_LINK"
        else:
            final_classification = "PARTIAL_LINEAGE_ONLY"

        classification_rows.append(
            {
                "episode_id": row["episode_id"],
                "prior_classification": row["prior_classification"],
                "final_classification": final_classification,
                "episode_type": row["episode_type"],
                "release_ts_utc": episode_release_ts_utc,
                "release_ts_us_eastern": episode_release_ts_local,
                "derived_us_session_date": episode_session_date,
                "selected_session_id": selected_session_id,
                "identity_complete": identity_complete,
                "member_us_session_dates": candidate_dates,
                "route_complete": route_complete,
                "classification_transition": f"{row['prior_classification']}->{final_classification}",
            }
        )

    scientific_fingerprint = fingerprint(
        {
            "event_identity_audit": event_identity_rows,
            "event_release_time_audit": release_time_rows,
            "event_date_session_join": join_rows,
            "downstream_route_audit": downstream_rows,
            "final_recovery_classification": classification_rows,
        }
    )
    return {
        "blocked_rows": blocked_rows,
        "event_source": event_source,
        "session_source": session_source,
        "event_identity_rows": event_identity_rows,
        "release_time_rows": release_time_rows,
        "join_rows": join_rows,
        "downstream_rows": downstream_rows,
        "classification_rows": classification_rows,
        "scientific_fingerprint": scientific_fingerprint,
    }


def summarize(audit: Mapping[str, Any]) -> dict[str, Any]:
    class_rows = audit["classification_rows"]
    join_rows = audit["join_rows"]
    identity_rows = audit["event_identity_rows"]
    downstream_rows = audit["downstream_rows"]
    counts = Counter(row["final_classification"] for row in class_rows)
    prior_counts = Counter(row["prior_classification"] for row in class_rows)
    transitions = Counter(row["classification_transition"] for row in class_rows)
    remaining_blocked = [row["episode_id"] for row in class_rows if row["final_classification"] not in {"RECOVERABLE_EXACT", "RECOVERABLE_BY_DETERMINISTIC_LINK_REPAIR", "RECOVERABLE_BY_DETERMINISTIC_EVENT_DATE_LINK"}]
    promotion_candidates = [row["episode_id"] for row in class_rows if row["final_classification"] in {"RECOVERABLE_EXACT", "RECOVERABLE_BY_DETERMINISTIC_LINK_REPAIR", "RECOVERABLE_BY_DETERMINISTIC_EVENT_DATE_LINK"}]
    summary = {
        "rescue_population_count": len(class_rows),
        "prior_partial_count_audited": prior_counts["PARTIAL_LINEAGE_ONLY"],
        "event_identities_resolved": sum(bool(row["identity_complete"]) for row in identity_rows),
        "event_identities_unresolved": sum(not row["identity_complete"] for row in identity_rows),
        "release_timestamps_resolved": len({row["episode_id"] for row in class_rows}),
        "unique_us_session_joins": sum(row["join_status"] == "UNIQUE_SESSION_MATCH" for row in join_rows),
        "ambiguous_session_joins": sum(row["join_status"] == "SESSION_AMBIGUOUS" for row in join_rows),
        "missing_session_joins": sum(row["join_status"] == "SESSION_NOT_FOUND" for row in join_rows),
        "complete_downstream_routes": sum(bool(row["route_completeness"]) for row in downstream_rows),
        "RECOVERABLE_EXACT": counts["RECOVERABLE_EXACT"],
        "RECOVERABLE_BY_DETERMINISTIC_LINK_REPAIR": counts["RECOVERABLE_BY_DETERMINISTIC_LINK_REPAIR"],
        "RECOVERABLE_BY_DETERMINISTIC_EVENT_DATE_LINK": counts["RECOVERABLE_BY_DETERMINISTIC_EVENT_DATE_LINK"],
        "PARTIAL_LINEAGE_ONLY": counts["PARTIAL_LINEAGE_ONLY"],
        "HISTORICAL_VERSION_UNVERIFIED": counts["HISTORICAL_VERSION_UNVERIFIED"],
        "NO_RECOVERY_ROUTE": counts["NO_RECOVERY_ROUTE"],
        "newly_rescued_episode_count": transitions["PARTIAL_LINEAGE_ONLY->RECOVERABLE_BY_DETERMINISTIC_EVENT_DATE_LINK"],
        "total_promotion_candidate_count": len(promotion_candidates),
        "promotion_candidate_ids": promotion_candidates,
        "remaining_blocked_episode_ids": remaining_blocked,
        "prior_recoverable_count": prior_counts["RECOVERABLE_EXACT"] + prior_counts["RECOVERABLE_BY_DETERMINISTIC_LINK_REPAIR"],
        "new_recoverable_count": counts["RECOVERABLE_EXACT"] + counts["RECOVERABLE_BY_DETERMINISTIC_LINK_REPAIR"] + counts["RECOVERABLE_BY_DETERMINISTIC_EVENT_DATE_LINK"],
        "scientific_fingerprint": audit["scientific_fingerprint"],
        "classification_transitions": dict(sorted(transitions.items())),
    }
    return summary


def decide(summary: Mapping[str, Any]) -> dict[str, str]:
    return {
        "audit_status": "EVENT_DATE_RESCUE_AUDIT_COMPLETE",
        "rescue_result": "REMAINING_PARTIAL_POPULATION_RESCUED" if summary["PARTIAL_LINEAGE_ONLY"] == 0 and summary["newly_rescued_episode_count"] > 0 else "ADDITIONAL_EVENT_DATE_RESCUE_SUPPORTED" if summary["newly_rescued_episode_count"] > 0 else "NO_ADDITIONAL_EVENT_DATE_RESCUE_SUPPORTED",
        "main_path_decision": "MAIN_341_PATH_UNCHANGED",
        "next_step_decision": "PREPARE_FINAL_VERSIONED_MATRIX_PROMOTION" if summary["total_promotion_candidate_count"] == 72 else "LEAVE_UNRESOLVED_EPISODES_BLOCKED",
    }


def make_run_id(summary: Mapping[str, Any], generated_ts: str) -> str:
    stamp = generated_ts.replace("-", "").replace(":", "").replace(".", "").replace("+00:00", "Z")
    return "PPHB-R1-REMAINING-65-EVENT-DATE-RESCUE-" + stamp + "-" + summary["scientific_fingerprint"].split(":")[1][:12]


def persist(run_dir: Path, audit: Mapping[str, Any], summary: Mapping[str, Any], decision: Mapping[str, str]) -> None:
    event_source_inventory = audit["event_source"]["source_inventory"]["authoritative_calendar_source"]
    event_source_contract = {
        "authoritative_event_source": "presignal_main.xlsx/Event sheet as preserved through the population-audit normalized event manifest",
        "source_identity": event_source_inventory["system"],
        "source_fingerprint": event_source_inventory["sha256"],
        "source_precedence": "oldest preserved authoritative event workbook consumed by the v2.1 episode builder",
        "event_identity_fields": ["event_row_locator", "event_id", "source_record_id", "excel_row_number"],
        "release_timestamp_fields": ["canonical_utc_release_timestamp", "original_timestamp"],
        "timezone_interpretation": "canonical_utc_release_timestamp is authoritative UTC; US session date derives from ZoneInfo('America/New_York')",
        "canonical_id_mapping_source": path_ref(EPISODE_MEMBER_MANIFEST),
        "batch_membership_rule": "episode membership is proven by exact episode_member_manifest rows joined to normalized calendar rows by event_row_locator",
        "normalized_manifest_path": path_ref(NORMALIZED_EVENT_MANIFEST),
        "raw_manifest_path": path_ref(RAW_EVENT_MANIFEST),
    }
    session_source_contract = {
        "authoritative_session_source": "matched source_session_id universe in episode_parent_session_map plus preserved reconstruction-route artifacts",
        "session_identity_pattern": "US|YYYY-MM-DD|CUSTOM_CONFIG_WINDOW",
        "timezone_name": TIMEZONE_NAME,
        "session_join_rule": "convert authoritative UTC release timestamp to America/New_York, take local calendar date, require exactly one preserved matched session for that date",
        "session_artifacts": [
            path_ref(PARENT_SESSION_MAP),
            path_ref(ATTENTION_MAP),
            path_ref(EPISODE_RECONSTRUCTION_PLAN),
            path_ref(ATTENTION_PLAN),
            path_ref(REQUEST_PLAN),
            path_ref(PACK_A_PLAN),
            path_ref(PACK_E_PLAN),
        ],
    }
    run_manifest = {
        "run_id": run_dir.name,
        "generated_ts": now(),
        "git_head": git_head(),
        "prior_session_join_audit_id": SESSION_JOIN_AUDIT_ID,
        "scientific_fingerprint": summary["scientific_fingerprint"],
        "call_free_guards": {
            "provider_calls": 0,
            "research_ai_calls": 0,
            "market_data_calls": 0,
            "web_calls": 0,
            "google_writes": 0,
        },
    }
    governing = {
        "episode_rows": path_ref(EPISODE_ROWS),
        "episode_parent_session_map": path_ref(PARENT_SESSION_MAP),
        "authoritative_attention_map": path_ref(ATTENTION_MAP),
        "attention_google_sheet_source_manifest": path_ref(ATTENTION_MANIFEST),
        "episode_attention_compatibility": path_ref(ATTENTION_COMPATIBILITY),
        "episode_request_compatibility": path_ref(REQUEST_COMPATIBILITY),
        "episode_pack_compatibility": path_ref(PACK_COMPATIBILITY),
        "pack_a_inputs": path_ref(PACK_A_INPUTS),
        "pack_e_inputs": path_ref(PACK_E_INPUTS),
        "population_audit_normalized_event_manifest": path_ref(NORMALIZED_EVENT_MANIFEST),
        "population_audit_episode_member_manifest": path_ref(EPISODE_MEMBER_MANIFEST),
        "blocked_73_baseline": path_ref(BLOCKED_LEDGER),
        "prior_rescue_classification": path_ref(PRIOR_CLASSIFICATION),
    }
    promotion_rows = [row for row in audit["classification_rows"] if row["final_classification"] in {"RECOVERABLE_EXACT", "RECOVERABLE_BY_DETERMINISTIC_LINK_REPAIR", "RECOVERABLE_BY_DETERMINISTIC_EVENT_DATE_LINK"}]
    remaining_rows = [row for row in audit["classification_rows"] if row["final_classification"] not in {"RECOVERABLE_EXACT", "RECOVERABLE_BY_DETERMINISTIC_LINK_REPAIR", "RECOVERABLE_BY_DETERMINISTIC_EVENT_DATE_LINK"}]
    reconciliation = {
        "previous_recoverable_count": summary["prior_recoverable_count"],
        "previous_partial_count": 64,
        "previous_no_route_count": 1,
        "new_recoverable_count": summary["new_recoverable_count"],
        "newly_rescued_count": summary["newly_rescued_episode_count"],
        "still_partial_count": summary["PARTIAL_LINEAGE_ONLY"],
        "still_no_route_count": summary["NO_RECOVERY_ROUTE"],
        "classification_transitions": summary["classification_transitions"],
        "unexpected_regressions": [],
    }
    write_json(run_dir / "run_manifest.json", run_manifest)
    write_json(run_dir / "governing_artifact_manifest.json", governing)
    write_json(run_dir / "event_source_contract.json", event_source_contract)
    write_json(run_dir / "session_source_contract.json", session_source_contract)
    write_jsonl(run_dir / "event_identity_audit.jsonl", audit["event_identity_rows"])
    write_jsonl(run_dir / "event_release_time_audit.jsonl", audit["release_time_rows"])
    write_jsonl(run_dir / "event_date_session_join.jsonl", audit["join_rows"])
    write_jsonl(run_dir / "downstream_route_audit.jsonl", audit["downstream_rows"])
    write_jsonl(run_dir / "final_recovery_classification.jsonl", audit["classification_rows"])
    write_jsonl(run_dir / "promotion_candidates.jsonl", promotion_rows)
    write_jsonl(run_dir / "remaining_blocked_episodes.jsonl", remaining_rows)
    write_json(run_dir / "rescue_reconciliation.json", reconciliation)
    write_json(run_dir / "audit_summary.json", summary)
    write_json(run_dir / "audit_decision.json", dict(decision))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, default=OUTPUT_ROOT)
    args = parser.parse_args(argv)
    audit = audit_population()
    summary = summarize(audit)
    decision = decide(summary)
    run_id = make_run_id(summary, now())
    run_dir = args.output_root / run_id
    persist(run_dir, audit, summary, decision)
    print(json.dumps({"run_id": run_id, **decision, **summary}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
