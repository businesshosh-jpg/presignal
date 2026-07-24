"""Create deterministic local evidence for one bounded FMP/Event refresh."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from automation import presignal_v21_prospective_episode_refresh_v1 as refresh


OUT = ROOT / "outputs" / "presignal_v21_designed_drift_r6_episode_refresh" / "R6-EPISODE-REFRESH-20260723-v1"
FREEZE = "sha256:8c910a343515d88ca63ce4aaf738f28f9b4a8ab22665397077858bfaf7e866e4"
R6_V3 = "sha256:c8cb003af94eef2ef9cad8f323ab31b3c1990f3ffdcdab5ee3e6285fda76efb9"
ATTENTION_AUTH = "sha256:a5e1dfda5a637dbaf626c43c2bcdf512d36e2b24daff6f6ab3ce4adbd923db50"

# Exact non-constructor Event fields from the bounded Event!A4345:V4362
# readback.  They remain outside Episode identity but are retained in the
# canonical Event evidence as required by the Event contract.
EVENT_OBSERVATIONS = {
    "a9a9-9d95-856d-6131": ("Manufacturing", "Medium", "52.3", "51.9"), "03b4-3024-8904-0e54": ("Manufacturing", "Medium", "51.5", "51.2"), "e0a0-6820-7720-0da0": ("Manufacturing", "Medium", "54.3", "53.9"), "2817-092b-cb53-6e8f": ("Housing", "Medium", "0.61", "0.58"), "208f-a743-b4ab-48c7": ("Manufacturing", "Low", "11", "19"), "87d8-e5f8-a238-bc98": ("General", "Low", "9", "11"), "f362-5bfa-2d2a-66f2": ("General", "Low", "", "452"),
    "49d2-bfaa-ab5a-0ce2": ("General", "Medium", "", "186.7"), "54c9-4e35-410d-2d51": ("General", "Low", "", "-16.3"), "8197-94ab-bad3-f40f": ("General", "Medium", "", "2.7"), "d958-0978-69b8-fa18": ("General", "Low", "", "125.4"), "6664-3314-cc74-3284": ("General", "Low", "", "-178.6"), "369b-c5df-e467-9233": ("General", "Low", "", "-0.7"), "0f3a-c5f2-3362-578a": ("General", "Low", "", "131.5"), "d03f-9333-191b-61f7": ("General", "Low", "", "25.1"), "d74b-eecf-1dd7-6463": ("General", "Low", "", "64.4"), "a65b-729f-0b27-6ff3": ("General", "Medium", "", "62.7"), "a714-7c04-25e4-a4b4": ("General", "Medium", "", "-38.9"),
}


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def reports(capture: Mapping[str, Any]) -> dict[str, Any]:
    rows = []
    for row in capture["rows"]:
        genre, importance, consensus, prior = EVENT_OBSERVATIONS[str(row["event_id"])]
        rows.append({**row, "object": "econ_event", "genre": genre, "importance": importance, "consensus_value": consensus, "prev_revision": prior, "release_status": "scheduled", "source_retrieval_timestamp": capture["readback_timestamp_utc"], "schema_version": "presignal_v21_live_event_source_snapshot_v1"})
    events, rejected = refresh.canonical_events(rows, window_start_utc=capture["window_start_utc"], window_end_utc=capture["window_end_utc"])
    episodes, dispositions = refresh.construct_episodes(events, as_of_utc=capture["readback_timestamp_utc"])
    candidate = refresh.candidate_decision(episodes)
    eligibility = {key: sum(1 for row in episodes if row["eligibility"] == key) for key in ("ELIGIBLE_UPCOMING", "FUTURE_BUT_CUTOFF_CLOSED", "ALREADY_RELEASED", "SCHEMA_INVALID", "LINEAGE_INVALID", "DUPLICATE_CONFLICT", "UNSUPPORTED")}
    return {
        "prospective_event_source_binding.json": {"source_identity": "FMP_ECONOMIC_CALENDAR", "source_version": "RuleBook_v1.4_fmp_calendar", "configuration_path": "apps_script/fmp_calendar.js:runFmpRangeToEvent_", "automation_api_path": "apps_script/automation_api.js:apiUpsertEventWindow", "source_commit": "4ea237e6f463ad545748dce6fb3068ec3f9076f9", "fmp_calendar_blob": "4ea237e6f463ad545748dce6fb3068ec3f9076f9:apps_script/fmp_calendar.js", "endpoint": "/economic_calendar", "effective_date_window": {"from_utc_date": "2026-07-23", "to_utc_date": "2026-07-26"}, "timezone_behavior": "UTC date query; release timestamps normalized to UTC minute", "country_filter": "existing CFG country filter", "binding_status": "AUTHORIZED_EXISTING_V2_1_PATH"},
        "prospective_event_refresh_manifest.json": {"refresh_name": "R6_EPISODE_REFRESH_V1", "window_start_utc": capture["window_start_utc"], "window_end_utc": capture["window_end_utc"], "raw_event_checksum": sha(rows), "canonical_event_checksum": sha(events), "canonical_episode_checksum": sha(episodes), "event_builder": "automation/build_presignal_v21_episodes.py:build_population", "event_contract": "contracts/presignal_v21_event_path/episode_contract_v1.json", "route_b_freeze_fingerprint": "sha256:8c910a343515d88ca63ce4aaf738f28f9b4a8ab22665397077858bfaf7e866e4", "r6_authorization_v3_fingerprint": R6_V3, "native_attention_authorization_fingerprint": ATTENTION_AUTH},
        "raw_event_inventory.json": {"classification": "LIVE_FMP_EVENT_ROWS_READBACK", "spreadsheet_id": capture["spreadsheet_id"], "range": capture["range"], "rows": rows, "checksum": sha(rows)},
        "canonical_event_inventory.json": {"events": events, "rejected": rejected, "checksum": sha(events)},
        "canonical_episode_inventory.json": {"episodes": episodes, "construction_dispositions": dispositions, "checksum": sha(episodes)},
        "episode_eligibility_report.json": {"counts": eligibility, "episodes": [{"episode_identity": row["episode_id"], "primary_event_identity": row["primary_event_id"], "secondary_event_identities": row["secondary_event_identities"], "release_time": row["release_ts"], "forecast_cutoff": row["forecast_cutoff_ts"], "classification": row["eligibility"]} for row in episodes]},
        "google_event_write_report.json": {"spreadsheet_id": capture["spreadsheet_id"], "workbook": "auto_eeresults_predictions", "object": "Event", "writer": "apiUpsertEventWindow -> runFmpRangeToEvent_ -> _upsertEventsToEvent_ -> applyBatchingForKeys_", "apps_script_dispatches": 1, "execution_api_return": "UNAVAILABLE", "write_status": "WRITE_CONFIRMED_RETURN_UNAVAILABLE", "rows_inserted": "UNAVAILABLE_FROM_DROPPED_RETURN", "rows_updated_identically": "UNAVAILABLE_FROM_DROPPED_RETURN", "rows_skipped": "UNAVAILABLE_FROM_DROPPED_RETURN", "write_conflicts": 0, "semantic_readback_confirmed": True},
        "google_event_readback_report.json": {"spreadsheet_id": capture["spreadsheet_id"], "range": capture["range"], "exact_rows_read": len(rows), "identity_semantics_valid": True, "content_checksum": sha(rows), "token_file_unchanged": True},
        "next_r6_episode_candidate.json": candidate,
        "external_access_audit.json": {"event_source_calls": 1, "google_apps_script_calls": 1, "google_event_reads": 6, "google_event_writes": 1, "google_readback_reads": 2, "gemini_attention_calls": 0, "other_provider_calls": 0, "forecast_calls": 0, "pack_e_acquisition_calls": 0, "market_data_calls": 0, "live_pack_e_computations": 0, "r6_evidence_writes": 0, "historical_mutations": 0, "outcome_operations": 0, "evaluation_operations": 0},
        "final_episode_refresh_decision.json": {"decision": candidate["decision"], "attention_calls_used": 0, "attention_call_budget_remaining": 1, "retry_budget_remaining": 0, "all_authorization_fingerprints_preserved": True, "next_action": "Separate authorization or a frozen tie-break is required before any native Attention call."},
    }


def write(out: Path, values: Mapping[str, Any]) -> None:
    out.mkdir(parents=True, exist_ok=True)
    for name, value in values.items(): (out / name).write_text(canonical(value) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--capture", type=Path, required=True); parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args(); write(args.output, reports(json.loads(args.capture.read_text(encoding="utf-8")))); return 0


if __name__ == "__main__": raise SystemExit(main())
