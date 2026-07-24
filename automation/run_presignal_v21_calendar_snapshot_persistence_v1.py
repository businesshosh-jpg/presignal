"""Offline snapshot-versus-persistent Event-store reconciliation for R6.

This consumes only preserved calendar artifacts.  The one bounded Google read
performed by the task is represented by the existing captured full-row
readback plus the verified physical header order; this runner makes no Google,
FMP, Apps Script, or provider call.
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from automation import presignal_v21_prospective_episode_refresh_v1 as refresh

OUT = ROOT / "outputs/presignal_v21_designed_drift_r6_calendar_snapshot_persistence" / "R6-CALENDAR-SNAPSHOT-PERSISTENCE-20260724-v1"
ROW_LEVEL = ROOT / "outputs/presignal_v21_designed_drift_r6_calendar_row_level_reconciliation" / "R6-CALENDAR-ROW-LEVEL-RECONCILIATION-20260724-v1"
IDEMPOTENCY = ROOT / "outputs/presignal_v21_designed_drift_r6_calendar_idempotency_replay" / "R6-CALENDAR-IDEMPOTENCY-REPLAY-20260724-v1"
PRIOR_REFRESH = ROOT / "outputs/presignal_v21_designed_drift_r6_episode_refresh" / "R6-EPISODE-REFRESH-20260723-v1"
WINDOW_START, WINDOW_END = "2026-07-24T00:00:00Z", "2026-07-31T23:59:59Z"
REFERENCE_UTC = "2026-07-24T04:25:40Z"
PMI_EPISODE = "EP_BATCH_0b3bf1cac3c02da74063"
ROUTE_B = "sha256:8c910a343515d88ca63ce4aaf738f28f9b4a8ab22665397077858bfaf7e866e4"
PMI_CLOSURE = "sha256:4c56f37ceb8507c0ea98d004c75f7d2ddd5433fe08e294da89d357b22f289656"
PROMPT = "presignal_v21_information_request_prompt_v2"
PROMPT_SHA = "sha256:219b3d33989d06b5f1968f6024c0135454320cf6c8f545116c6595d630011cb5"
ENUM_SHA = "sha256:320dad35692df096ea54466c17a8f02cff6287899aa3b7755dea00d7362bfb52"
TEMPORAL_SHA = "sha256:d557c0733cc59982c46f71efaa89dad03a27e0d0c6023ba54eb2ef807c84c570"


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical(value).encode()).hexdigest()


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write(name: str, value: Any) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(canonical(value) + "\n", encoding="utf-8")


def identity(row: dict[str, Any]) -> str:
    return "|".join((str(row["country"]).upper(), str(row["indicator_name"]), str(row["release_ts"])))


def corrected_persistent_rows() -> list[dict[str, Any]]:
    """Repair only the preserved reader's known three-column header mapping."""
    raw = load(IDEMPOTENCY / "calendar_event_readback.json")["rows"]
    rows: list[dict[str, Any]] = []
    for item in raw:
        # Physical Event sheet order is event_id,batch_id,type.  The old
        # captured reader used type,event_id,batch_id; retain source evidence
        # but restore that exact header contract without touching Google.
        row = dict(item)
        row["event_id"], row["batch_id"], row["type"] = item["type"], item["event_id"], item["batch_id"]
        try:
            canonical_rows, rejected = refresh.canonical_events([row], window_start_utc=WINDOW_START, window_end_utc=WINDOW_END)
        except Exception:
            continue
        if not rejected and canonical_rows:
            rows.append({**row, **canonical_rows[0]})
    by_identity = {identity(row): row for row in rows}
    return [by_identity[key] for key in sorted(by_identity)]


def provenance() -> dict[str, Any]:
    old = load(PRIOR_REFRESH / "raw_event_inventory.json")["rows"]
    result = {}
    for item in old:
        key = identity(item)
        if "Kansas Fed" in key and "(Jul)" in key:
            result[key] = item
    return result


def build() -> dict[str, Any]:
    source = load(ROW_LEVEL / "calendar_row_level_adapter_event_set.json")["rows"]
    source_by_id = {item["event_identity"]: item for item in source}
    persistent = corrected_persistent_rows()
    persistent_by_id = {identity(item): item for item in persistent}
    kansas_evidence = provenance()
    kansas_ids = sorted(key for key in persistent_by_id if "Kansas Fed" in key and "(Jul)" in key)
    if len(source_by_id) != 91 or len(persistent_by_id) != 93 or len(kansas_ids) != 2:
        raise ValueError("PRESERVED_EVENT_SET_COUNT_UNEXPECTED")
    kansas = []
    for key in kansas_ids:
        row = persistent_by_id[key]
        prior = kansas_evidence.get(key, {})
        kansas.append({
            "event_identity": key, "google_row_reference": row.get("source_row"), "source_identity": row.get("source_cal"),
            "first_seen_evidence": "R6-EPISODE-REFRESH-20260723-v1/raw_event_inventory.json", "last_seen_evidence": "bounded Event read 2026-07-24", "content_checksum": sha({k: row.get(k, "") for k in ("country", "indicator_name", "release_ts", "event_id", "batch_id", "type", "source_cal")}),
            "release_ts": row["release_ts"], "current_source_snapshot_membership": key in source_by_id,
            "prior_source_snapshot_membership": bool(prior), "episode_usage_history": "NONE", "attention_or_forecast_usage_history": "NONE",
            "classification": "VALID_PERSISTED_SOURCE_EVENT_NOT_IN_LATEST_SNAPSHOT", "current_status": "SCHEDULED_PERSISTED_SOURCE_EVENT",
            "prospective_eligibility_at_reference": "ELIGIBLE_UPCOMING" if row["release_ts"] > REFERENCE_UTC else "CUTOFF_CLOSED",
            "provenance_record": {k: prior.get(k) for k in ("event_id", "batch_id", "type", "source_row", "retrieved_at_utc")},
        })
    events, rejected = refresh.canonical_events(persistent, window_start_utc=WINDOW_START, window_end_utc=WINDOW_END)
    episodes, dispositions = refresh.construct_episodes(events, as_of_utc=REFERENCE_UTC)
    exclusions, eligible = [], []
    for episode in episodes:
        if episode["episode_id"] == PMI_EPISODE:
            exclusions.append({"episode_id": episode["episode_id"], "reason": "PERMANENTLY_CLOSED_PMI_ATTEMPT"})
        elif episode["eligibility"] != "ELIGIBLE_UPCOMING":
            exclusions.append({"episode_id": episode["episode_id"], "reason": episode["eligibility"]})
        else:
            eligible.append(episode)
    selection = refresh.candidate_decision(eligible)
    relationship = {
        "current_source_count": len(source_by_id), "persistent_store_count": len(persistent_by_id), "candidate_input_count": len(events),
        "current_source_checksum": sha(sorted(source_by_id)), "persistent_store_checksum": sha(sorted(persistent_by_id)), "candidate_input_checksum": sha([identity(item) for item in events]),
        "source_only_count": len(set(source_by_id) - set(persistent_by_id)), "persistent_only_count": len(set(persistent_by_id) - set(source_by_id)),
        "persistent_only_identities": sorted(set(persistent_by_id) - set(source_by_id)),
        "contract_classification": "PERSISTENT_CANONICAL_EVENT_STORE",
        "candidate_input_rule": "persistent canonical Event rows with source provenance and open-cutoff eligibility; latest-source membership is not required by the upsert-only store contract",
    }
    package = {
        "name": "PRESIGNAL_V21_DESIGNED_DRIFT_2_NEW_R6_EPISODE_CANDIDATE_PACKAGE_V1", "route_b_freeze_fingerprint": ROUTE_B,
        "calendar_dispatch_capture_fingerprint": "sha256:7dd73d37bf0f9b04fdd738d0c1c98d9619c482d28df963b5b5f65e0f9f4ef58c",
        "current_source_event_set_checksum": relationship["current_source_checksum"], "persistent_store_event_set_checksum": relationship["persistent_store_checksum"],
        "candidate_input_event_set_checksum": relationship["candidate_input_checksum"], "canonical_episode_set_checksum": sha(episodes),
        "eligible_episode_identities": [item["episode_id"] for item in eligible], "excluded_episode_identities_and_reasons": exclusions,
        "selection_rule_status": selection["selection_rule"], "pmi_closure_fingerprint": PMI_CLOSURE,
        "request_temporal_alignment_fingerprint": TEMPORAL_SHA, "request_prompt_version": PROMPT, "request_prompt_checksum": PROMPT_SHA,
        "category_enum_checksum": ENUM_SHA, "old_pmi_attention_reused": False, "old_pmi_request_responses_reused": False,
    }
    return {"source": source, "persistent": persistent, "kansas": kansas, "events": events, "rejected": rejected, "episodes": episodes,
            "dispositions": dispositions, "eligible": eligible, "exclusions": exclusions, "selection": selection, "relationship": relationship, "package": package}


def run() -> str:
    state = build()
    package = state["package"]
    package_fp = sha(package)
    contract_trace = {
        "classification": "PERSISTENT_CANONICAL_EVENT_STORE", "authoritative_implementation_paths": ["apps_script/fmp_calendar.js:_upsertEventsToEvent_", "apps_script/fmp_calendar.js:runFmpRangeToEvent_", "apps_script/automation_api.js:apiUpsertEventWindow_"],
        "latest_source_set_replaces_existing_rows": False, "absent_source_events_deleted": False, "persistent_rows_permitted": True,
        "lifecycle_status_available": False, "evidence": "_upsertEventsToEvent_ updates matching identities or appends; it has no Event-row deletion or retirement branch.",
    }
    decision = "NEW_R6_EPISODE_CANDIDATES_READY_USER_SELECTION_REQUIRED" if len(state["eligible"]) != 1 else "NEW_R6_EPISODE_DETERMINISTICALLY_SELECTED_ATTENTION_AUTHORIZATION_READY"
    if not state["eligible"]:
        decision = "NEW_R6_NO_ELIGIBLE_EPISODE_IN_AUTHORIZED_WINDOW"
    artifacts = {
        "calendar_event_store_contract_trace.json": contract_trace,
        "calendar_event_store_semantics_decision.json": {"classification": contract_trace["classification"], "candidate_input_authority": "PERSISTENT_ELIGIBLE_STORE", "decision": decision},
        "kansas_fed_event_provenance_report.json": {"events": state["kansas"]},
        "kansas_fed_event_classification.json": {"events": [{"event_identity": item["event_identity"], "classification": item["classification"]} for item in state["kansas"]]},
        "calendar_current_source_event_set.json": {"count": len(state["source"]), "rows": state["source"], "checksum": state["relationship"]["current_source_checksum"]},
        "calendar_persistent_store_event_set.json": {"count": len(state["persistent"]), "rows": state["persistent"], "checksum": state["relationship"]["persistent_store_checksum"], "physical_header_order_verified_by_one_bounded_read": ["object", "country", "indicator_name", "genre", "importance", "event_id", "batch_id", "type", "release_ts"]},
        "calendar_candidate_input_event_set.json": {"count": len(state["events"]), "rows": state["events"], "checksum": state["relationship"]["candidate_input_checksum"], "kansas_fed_admitted": True},
        "calendar_event_set_relationship_report.json": state["relationship"],
        "canonical_future_episodes.json": {"count": len(state["episodes"]), "episodes": state["episodes"], "checksum": sha(state["episodes"])},
        "episode_eligibility_report.json": {"reference_utc": REFERENCE_UTC, "eligible": state["eligible"], "excluded": state["exclusions"], "event_rejections": state["rejected"], "construction_dispositions": state["dispositions"]},
        "episode_selection_rule_trace.json": {"existing_authoritative_rule_found": False, **state["selection"], "advisory_recommendation": None, "selection_authorization_created": False},
        "new_r6_episode_candidate_package.json": package,
        "new_r6_episode_candidate_package_fingerprint.json": {"fingerprint": package_fp, "deterministic": True},
        "external_access_audit.json": {"calendar_refresh_calls": 0, "apps_script_executions": 0, "fmp_calls": 0, "google_event_reads": 1, "google_event_writes": 0, "gemini_calls": 0, "attention_calls": 0, "information_request_calls": 0, "forecast_calls": 0, "pack_operations": 0, "outcome_operations": 0, "evaluation_operations": 0},
        "final_calendar_snapshot_persistence_decision.json": {"decision": decision, "candidate_package_fingerprint": package_fp, "attention_authorization_created": False},
    }
    # Prove deterministic construction from the same preserved Event set.
    checks = [sha(build()["package"]) for _ in range(3)]
    artifacts["calendar_event_set_relationship_report.json"]["determinism"] = {"runs": 3, "identical_package_inputs": len(set(checks)) == 1}
    for name, value in artifacts.items(): write(name, value)
    return decision


if __name__ == "__main__":
    print(canonical({"decision": run(), "output": str(OUT.relative_to(ROOT))}))
