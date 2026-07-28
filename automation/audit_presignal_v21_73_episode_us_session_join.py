#!/usr/bin/env python3
"""Audit blocked Episodes via deterministic US Eastern session-date joins."""
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
ELIGIBILITY_CONTRACT_ID = "PPHB-R1-ELIGIBILITY-CONTRACT-20260728T132116Z-88a316711419"
ELIGIBILITY_IMPLEMENTATION_ID = "PPHB-R1-ELIGIBILITY-IMPLEMENTATION-20260728T132849Z-297192188403"
RECONSTRUCTION_DRY_RUN_ID = "PPHB-R1-RECONSTRUCTION-DRY-RUN-20260728T134639Z-b3c9532ef93e"
PILOT_ID = "PPHB-R1-73-EPISODE-RESCUE-PILOT-20260728T142857Z-473c386ab38a"

STEP5_ROOT = ROOT / "outputs" / "presignal_v21_step5_reuse"
ATTENTION_ROOT = ROOT / "outputs" / "presignal_v21_attention_preservation"
RECONSTRUCTION_ROOT = ROOT / "outputs" / "presignal_v21_full_round_1_reconstruction_dry_run" / RECONSTRUCTION_DRY_RUN_ID
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

TIMEZONE_NAME = "America/New_York"
SESSION_WINDOW_NAME = "CUSTOM_CONFIG_WINDOW"
COUNTRY = "US"

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


def parse_utc_timestamp(value: str) -> datetime:
    if not value:
        raise ValueError("UTC_TIMESTAMP_REQUIRED")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("UTC_TIMESTAMP_MUST_BE_TIMEZONE_AWARE")
    return parsed.astimezone(timezone.utc)


def derive_us_session_date(release_ts_utc: str) -> dict[str, str]:
    utc_dt = parse_utc_timestamp(release_ts_utc)
    local_dt = utc_dt.astimezone(ZoneInfo(TIMEZONE_NAME))
    return {
        "release_ts_utc": utc_dt.isoformat().replace("+00:00", "Z"),
        "release_ts_us_eastern": local_dt.isoformat(),
        "derived_us_session_date": local_dt.date().isoformat(),
        "timezone_name": TIMEZONE_NAME,
        "utc_offset_applied": local_dt.strftime("%z")[:3] + ":" + local_dt.strftime("%z")[3:],
    }


def expected_session_id_for_date(session_date: str) -> str:
    return f"{COUNTRY}|{session_date}|{SESSION_WINDOW_NAME}"


def load_blocked_population() -> list[dict[str, Any]]:
    blocked_rows = read_jsonl(BLOCKED_LEDGER)
    episode_rows = {row["episode_id"]: row for row in read_jsonl(EPISODE_ROWS)}
    merged: list[dict[str, Any]] = []
    for row in blocked_rows:
        episode = episode_rows[row["episode_id"]]
        merged.append(
            {
                "episode_id": row["episode_id"],
                "episode_type": "BATCH" if episode.get("same_time_cluster_flag") else "STANDALONE",
                "member_event_ids": list(episode["member_event_ids"]),
                "member_event_count": int(episode["member_event_count"]),
                "release_ts": episode["release_ts"],
                "forecast_cutoff_ts": episode["forecast_cutoff_ts"],
                "source_session_status": row["source_session_status"],
                "source_session_reason": row["source_session_reason"],
                "attention_status": row["attention_status"],
                "pack_a_status": row["pack_a_status"],
                "pack_e_status": row["pack_e_status"],
                "historical_source_lineage_status": row["historical_source_lineage_status"],
            }
        )
    merged.sort(key=lambda row: (row["release_ts"], row["episode_id"]))
    if len(merged) != 73:
        raise ValueError("BLOCKED_EPISODE_COUNT_NOT_73")
    if len({row["episode_id"] for row in merged}) != 73:
        raise ValueError("BLOCKED_EPISODE_IDS_NOT_UNIQUE")
    return merged


def build_session_universe() -> dict[str, Any]:
    matched_parent_rows = [row for row in read_jsonl(PARENT_SESSION_MAP) if row.get("status") == "MATCHED" and row.get("source_session_id")]
    session_ids = sorted({row["source_session_id"] for row in matched_parent_rows})
    by_date: dict[str, list[str]] = defaultdict(list)
    supporting_paths: dict[str, set[str]] = defaultdict(set)
    for row in matched_parent_rows:
        session_id = row["source_session_id"]
        by_date[session_id.split("|")[1]].append(session_id)
        supporting_paths[session_id].add(path_ref(PARENT_SESSION_MAP))
    for path in (PACK_A_INPUTS, PACK_E_INPUTS):
        for row in read_jsonl(path):
            session_id = row.get("source_session_id")
            if not session_id:
                continue
            supporting_paths[session_id].add(path_ref(path))
    for row in read_jsonl(ATTENTION_MAP):
        session_id = row.get("active_session_id") or row.get("session_id")
        if not session_id:
            continue
        supporting_paths[session_id].add(path_ref(ATTENTION_MAP))
    return {
        "matched_parent_rows": matched_parent_rows,
        "session_ids": session_ids,
        "session_ids_by_date": {key: sorted(set(value)) for key, value in by_date.items()},
        "supporting_paths": {key: sorted(value) for key, value in supporting_paths.items()},
    }


def build_member_evidence() -> dict[str, Any]:
    member_ids_by_session: dict[str, set[str]] = defaultdict(set)
    evidence_paths_by_session: dict[str, set[str]] = defaultdict(set)
    for path in (PACK_A_INPUTS, PACK_E_INPUTS):
        for row in read_jsonl(path):
            session_id = row.get("source_session_id")
            if not session_id:
                continue
            for member in row.get("episode_members", []):
                event_id = member.get("event_id")
                if event_id:
                    member_ids_by_session[session_id].add(event_id)
                    evidence_paths_by_session[session_id].add(path_ref(path))
    for row in read_jsonl(ATTENTION_MAP):
        session_id = row.get("active_session_id") or row.get("session_id")
        event_id = row.get("event_id")
        if session_id and event_id:
            member_ids_by_session[session_id].add(event_id)
            evidence_paths_by_session[session_id].add(path_ref(ATTENTION_MAP))
    return {
        "member_ids_by_session": member_ids_by_session,
        "evidence_paths_by_session": {key: sorted(value) for key, value in evidence_paths_by_session.items()},
    }


def build_downstream_evidence() -> dict[str, Any]:
    attention_rows = read_jsonl(ATTENTION_MAP)
    attention_rows_by_session: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in attention_rows:
        session_id = row.get("active_session_id") or row.get("session_id")
        if session_id:
            attention_rows_by_session[session_id].append(row)

    pack_a_rows_by_session: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in read_jsonl(PACK_A_INPUTS):
        session_id = row.get("source_session_id")
        if session_id:
            pack_a_rows_by_session[session_id].append(row)

    pack_e_rows_by_session: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in read_jsonl(PACK_E_INPUTS):
        session_id = row.get("source_session_id")
        if session_id:
            pack_e_rows_by_session[session_id].append(row)

    return {
        "attention_rows_by_session": attention_rows_by_session,
        "pack_a_rows_by_session": pack_a_rows_by_session,
        "pack_e_rows_by_session": pack_e_rows_by_session,
    }


def classify_episode(*, join_status: str, membership_complete: bool, downstream_complete: bool, explicit_parent_match: bool) -> str:
    if join_status != "UNIQUE_SESSION_MATCH":
        return "NO_RECOVERY_ROUTE"
    if explicit_parent_match and membership_complete and downstream_complete:
        return "RECOVERABLE_EXACT"
    if membership_complete and downstream_complete:
        return "RECOVERABLE_BY_DETERMINISTIC_LINK_REPAIR"
    if membership_complete or not downstream_complete:
        return "PARTIAL_LINEAGE_ONLY"
    return "PARTIAL_LINEAGE_ONLY"


def audit_blocked_population() -> dict[str, Any]:
    blocked_rows = load_blocked_population()
    session_universe = build_session_universe()
    member_evidence = build_member_evidence()
    downstream_evidence = build_downstream_evidence()
    attention_manifest = read_json(ATTENTION_MANIFEST)

    matched_parent_episode_ids = {
        row["episode_id"] for row in session_universe["matched_parent_rows"]
    }

    timezone_rows: list[dict[str, Any]] = []
    join_rows: list[dict[str, Any]] = []
    membership_rows: list[dict[str, Any]] = []
    downstream_rows: list[dict[str, Any]] = []
    classification_rows: list[dict[str, Any]] = []
    promotion_rows: list[dict[str, Any]] = []
    remaining_rows: list[dict[str, Any]] = []

    session_ids_by_date = session_universe["session_ids_by_date"]
    member_ids_by_session = member_evidence["member_ids_by_session"]

    for row in blocked_rows:
        conversion = derive_us_session_date(row["release_ts"])
        timezone_rows.append(
            {
                "episode_id": row["episode_id"],
                "release_ts_source": path_ref(EPISODE_ROWS),
                **conversion,
                "conversion_status": "OK",
            }
        )

        session_date = conversion["derived_us_session_date"]
        candidate_session_ids = session_ids_by_date.get(session_date, [])
        expected_session_id = expected_session_id_for_date(session_date)
        selected_session_id = candidate_session_ids[0] if len(candidate_session_ids) == 1 else ""
        join_status = (
            "UNIQUE_SESSION_MATCH"
            if len(candidate_session_ids) == 1
            else "SESSION_NOT_FOUND"
            if len(candidate_session_ids) == 0
            else "SESSION_AMBIGUOUS"
        )
        selection_rule = (
            "select the unique preserved source_session_id whose US session date equals the America/New_York local date"
            if join_status == "UNIQUE_SESSION_MATCH"
            else "no automatic selection"
        )
        join_rows.append(
            {
                "episode_id": row["episode_id"],
                "derived_us_session_date": session_date,
                "expected_session_id_pattern": expected_session_id,
                "candidate_session_ids": candidate_session_ids,
                "candidate_count": len(candidate_session_ids),
                "selected_session_id": selected_session_id,
                "join_status": join_status,
                "selection_rule": selection_rule,
                "supporting_artifact": path_ref(PARENT_SESSION_MAP),
                "supporting_session_artifacts": session_universe["supporting_paths"].get(selected_session_id, []),
            }
        )

        expected_member_ids = list(row["member_event_ids"])
        matched_member_ids = sorted(
            event_id for event_id in expected_member_ids if event_id in member_ids_by_session.get(selected_session_id, set())
        )
        missing_member_ids = sorted(set(expected_member_ids) - set(matched_member_ids))
        membership_complete = bool(selected_session_id) and not missing_member_ids
        membership_rows.append(
            {
                "episode_id": row["episode_id"],
                "selected_session_id": selected_session_id,
                "expected_member_event_ids": expected_member_ids,
                "matched_member_event_ids": matched_member_ids,
                "missing_member_event_ids": missing_member_ids,
                "membership_complete": membership_complete,
                "membership_evidence_artifacts": member_evidence["evidence_paths_by_session"].get(selected_session_id, []),
            }
        )

        attention_rows = downstream_evidence["attention_rows_by_session"].get(selected_session_id, [])
        pack_a_rows = downstream_evidence["pack_a_rows_by_session"].get(selected_session_id, [])
        pack_e_rows = downstream_evidence["pack_e_rows_by_session"].get(selected_session_id, [])
        attention_providers = sorted({row.get("provider") for row in attention_rows if row.get("provider")})
        pack_a_providers = sorted({row.get("provider") for row in pack_a_rows if row.get("provider")})
        pack_e_providers = sorted({row.get("provider") for row in pack_e_rows if row.get("provider")})
        request_lineage_preserved = bool(pack_a_rows or pack_e_rows)
        downstream_complete = bool(attention_rows and pack_a_rows and pack_e_rows)
        downstream_rows.append(
            {
                "episode_id": row["episode_id"],
                "selected_session_id": selected_session_id,
                "attention_lineage_status": "PRESERVED" if attention_rows else "MISSING",
                "attention_artifact_references": [path_ref(ATTENTION_MAP)] if attention_rows else [],
                "attention_provider_coverage": attention_providers,
                "information_request_lineage_status": "PRESERVED" if request_lineage_preserved else "MISSING",
                "information_request_artifact_references": sorted(
                    {path_ref(PACK_A_INPUTS) for _ in pack_a_rows} | {path_ref(PACK_E_INPUTS) for _ in pack_e_rows}
                ) if request_lineage_preserved else [],
                "pack_a_lineage_status": "PRESERVED" if pack_a_rows else "MISSING",
                "pack_a_artifact_references": [path_ref(PACK_A_INPUTS)] if pack_a_rows else [],
                "pack_a_provider_coverage": pack_a_providers,
                "pack_e_lineage_status": "PRESERVED" if pack_e_rows else "MISSING",
                "pack_e_artifact_references": [path_ref(PACK_E_INPUTS)] if pack_e_rows else [],
                "pack_e_provider_coverage": pack_e_providers,
                "complete_downstream_lineage_route": downstream_complete,
            }
        )

        explicit_parent_match = row["episode_id"] in matched_parent_episode_ids
        classification = classify_episode(
            join_status=join_status,
            membership_complete=membership_complete,
            downstream_complete=downstream_complete,
            explicit_parent_match=explicit_parent_match,
        )
        repair_rule = ""
        if classification == "RECOVERABLE_BY_DETERMINISTIC_LINK_REPAIR":
            repair_rule = (
                "Convert authoritative UTC release_ts to America/New_York, derive the local calendar date, "
                "select the unique preserved session_id for that date from the matched parent-session universe, "
                "verify every episode member_event_id against preserved session-member evidence, then bind the "
                "episode to that session_id only when preserved Attention and Pack A/E lineage also exist."
            )
        record = {
            "episode_id": row["episode_id"],
            "episode_type": row["episode_type"],
            "release_ts": row["release_ts"],
            "derived_us_session_date": session_date,
            "selected_session_id": selected_session_id,
            "join_status": join_status,
            "membership_complete": membership_complete,
            "complete_downstream_lineage_route": downstream_complete,
            "recovery_classification": classification,
            "deterministic_repair_rule": repair_rule,
            "original_blocker": row["source_session_reason"],
        }
        classification_rows.append(record)
        if classification in {"RECOVERABLE_EXACT", "RECOVERABLE_BY_DETERMINISTIC_LINK_REPAIR"}:
            promotion_rows.append(record)
        else:
            remaining_rows.append(record)

    scientific_fingerprint = fingerprint(
        {
            "timezone_conversion_audit": timezone_rows,
            "session_date_join_audit": join_rows,
            "episode_membership_verification": membership_rows,
            "downstream_lineage_verification": downstream_rows,
            "recovery_classification": classification_rows,
        }
    )
    return {
        "blocked_rows": blocked_rows,
        "timezone_rows": timezone_rows,
        "join_rows": join_rows,
        "membership_rows": membership_rows,
        "downstream_rows": downstream_rows,
        "classification_rows": classification_rows,
        "promotion_rows": promotion_rows,
        "remaining_rows": remaining_rows,
        "session_universe": session_universe,
        "attention_manifest": attention_manifest,
        "scientific_fingerprint": scientific_fingerprint,
    }


def summarize(audit: Mapping[str, Any]) -> dict[str, Any]:
    join_rows = audit["join_rows"]
    membership_rows = audit["membership_rows"]
    downstream_rows = audit["downstream_rows"]
    class_rows = audit["classification_rows"]
    counts = Counter(row["recovery_classification"] for row in class_rows)
    unique_joins = sum(row["join_status"] == "UNIQUE_SESSION_MATCH" for row in join_rows)
    ambiguous_joins = sum(row["join_status"] == "SESSION_AMBIGUOUS" for row in join_rows)
    missing_joins = sum(row["join_status"] == "SESSION_NOT_FOUND" for row in join_rows)
    membership_complete = sum(bool(row["membership_complete"]) for row in membership_rows)
    downstream_complete = sum(bool(row["complete_downstream_lineage_route"]) for row in downstream_rows)
    promotion_count = counts["RECOVERABLE_EXACT"] + counts["RECOVERABLE_BY_DETERMINISTIC_LINK_REPAIR"]
    summary = {
        "total_blocked_population": len(class_rows),
        "release_timestamps_resolved": len(audit["timezone_rows"]),
        "us_session_dates_derived": len(audit["timezone_rows"]),
        "unique_session_date_joins": unique_joins,
        "ambiguous_session_date_joins": ambiguous_joins,
        "missing_session_date_joins": missing_joins,
        "complete_membership_matches": membership_complete,
        "incomplete_membership_matches": len(membership_rows) - membership_complete,
        "complete_downstream_lineage_routes": downstream_complete,
        "RECOVERABLE_EXACT": counts["RECOVERABLE_EXACT"],
        "RECOVERABLE_BY_DETERMINISTIC_LINK_REPAIR": counts["RECOVERABLE_BY_DETERMINISTIC_LINK_REPAIR"],
        "PARTIAL_LINEAGE_ONLY": counts["PARTIAL_LINEAGE_ONLY"],
        "HISTORICAL_VERSION_UNVERIFIED": counts["HISTORICAL_VERSION_UNVERIFIED"],
        "NO_RECOVERY_ROUTE": counts["NO_RECOVERY_ROUTE"],
        "promotion_candidate_count": promotion_count,
        "remaining_blocked_count": len(class_rows) - promotion_count,
        "scientific_fingerprint": audit["scientific_fingerprint"],
    }
    return summary


def make_run_id(summary: Mapping[str, Any], generated_ts: str) -> str:
    stamp = generated_ts.replace("-", "").replace(":", "").replace("+00:00", "Z").replace(".", "")
    stamp = stamp.replace("T", "T").replace("Z", "Z")
    return "PPHB-R1-73-EPISODE-US-SESSION-JOIN-AUDIT-" + stamp + "-" + summary["scientific_fingerprint"].split(":")[1][:12]


def make_decision(summary: Mapping[str, Any]) -> dict[str, str]:
    if summary["release_timestamps_resolved"] != 73 or summary["us_session_dates_derived"] != 73:
        audit_status = "US_SESSION_JOIN_AUDIT_PARTIALLY_COMPLETE"
    else:
        audit_status = "US_SESSION_JOIN_AUDIT_COMPLETE"
    promotion_count = summary["promotion_candidate_count"]
    rescue_result = (
        "DETERMINISTIC_SESSION_DATE_RESCUE_SUPPORTED"
        if promotion_count >= 7
        else "LIMITED_SESSION_DATE_RESCUE_SUPPORTED"
        if promotion_count >= 1
        else "SESSION_DATE_RESCUE_NOT_SUPPORTED"
    )
    return {
        "audit_status": audit_status,
        "rescue_result": rescue_result,
        "main_path_decision": "MAIN_341_PATH_UNCHANGED",
        "next_step_decision": "PREPARE_VERSIONED_MATRIX_PROMOTION" if promotion_count else "LEAVE_NONMATCHING_EPISODES_BLOCKED",
    }


def persist(run_dir: Path, audit: Mapping[str, Any], summary: Mapping[str, Any], decision: Mapping[str, str]) -> None:
    run_manifest = {
        "run_id": run_dir.name,
        "generated_ts": now(),
        "git_head": git_head(),
        "governing_artifacts": {
            "population_audit_id": POPULATION_AUDIT_ID,
            "eligibility_contract_id": ELIGIBILITY_CONTRACT_ID,
            "eligibility_implementation_id": ELIGIBILITY_IMPLEMENTATION_ID,
            "reconstruction_dry_run_id": RECONSTRUCTION_DRY_RUN_ID,
            "rescue_pilot_id": PILOT_ID,
        },
        "call_free_guards": {
            "provider_calls": 0,
            "research_ai_calls": 0,
            "market_data_calls": 0,
            "web_calls": 0,
            "google_writes": 0,
        },
        "scientific_fingerprint": summary["scientific_fingerprint"],
    }
    governing_manifest = {
        "episode_rows": path_ref(EPISODE_ROWS),
        "episode_parent_session_map": path_ref(PARENT_SESSION_MAP),
        "episode_attention_compatibility": path_ref(ATTENTION_COMPATIBILITY),
        "episode_request_compatibility": path_ref(REQUEST_COMPATIBILITY),
        "episode_pack_compatibility": path_ref(PACK_COMPATIBILITY),
        "event_path_forecast_inputs_pack_a": path_ref(PACK_A_INPUTS),
        "event_path_forecast_inputs_pack_e": path_ref(PACK_E_INPUTS),
        "authoritative_attention_map": path_ref(ATTENTION_MAP),
        "attention_google_sheet_source_manifest": path_ref(ATTENTION_MANIFEST),
        "blocked_73_baseline": path_ref(BLOCKED_LEDGER),
        "scientific_fingerprint": summary["scientific_fingerprint"],
    }
    session_definition_contract = {
        "session_semantic_definition": "one US economic-calendar session per America/New_York calendar date",
        "timezone_name": TIMEZONE_NAME,
        "date_derivation_rule": "convert authoritative release_ts UTC to America/New_York and take the local calendar date",
        "authoritative_session_artifact": path_ref(PARENT_SESSION_MAP),
        "supporting_session_semantics_artifacts": [
            path_ref(ATTENTION_MANIFEST),
            path_ref(ATTENTION_MAP),
        ],
        "session_identity_fields": ["country", "session_date", "session_window_name"],
        "session_identity_pattern": "US|YYYY-MM-DD|CUSTOM_CONFIG_WINDOW",
        "uniqueness_rule": "exactly one MATCHED source_session_id in the preserved parent-session universe may match a derived US session date",
        "membership_rule": "every episode member_event_id must be present in preserved session-member evidence for the selected session_id",
        "ambiguity_behavior": "if zero or multiple preserved session_ids match the derived US session date, do not select automatically",
    }
    write_json(run_dir / "run_manifest.json", run_manifest)
    write_json(run_dir / "governing_artifact_manifest.json", governing_manifest)
    write_json(run_dir / "session_definition_contract.json", session_definition_contract)
    write_jsonl(run_dir / "timezone_conversion_audit.jsonl", audit["timezone_rows"])
    write_jsonl(run_dir / "session_date_join_audit.jsonl", audit["join_rows"])
    write_jsonl(run_dir / "episode_membership_verification.jsonl", audit["membership_rows"])
    write_jsonl(run_dir / "downstream_lineage_verification.jsonl", audit["downstream_rows"])
    write_jsonl(run_dir / "recovery_classification.jsonl", audit["classification_rows"])
    write_jsonl(run_dir / "rescue_promotion_candidates.jsonl", audit["promotion_rows"])
    write_jsonl(run_dir / "remaining_blocked_episodes.jsonl", audit["remaining_rows"])
    write_json(run_dir / "audit_summary.json", summary)
    write_json(run_dir / "audit_decision.json", dict(decision))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, default=OUTPUT_ROOT)
    args = parser.parse_args(argv)

    audit = audit_blocked_population()
    summary = summarize(audit)
    generated_ts = now()
    run_id = make_run_id(summary, generated_ts)
    run_dir = args.output_root / run_id
    decision = make_decision(summary)
    persist(run_dir, audit, summary, decision)
    print(json.dumps({"run_id": run_id, **decision, **summary}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
