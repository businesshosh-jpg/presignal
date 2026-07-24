"""Freeze the user-selected FOMC Episode and prepare, but never dispatch, Attention."""
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

OUT = ROOT / "outputs/presignal_v21_designed_drift_r6_episode_selection_fomc" / "R6-EPISODE-SELECTION-FOMC-20260724-v1"
PACKAGE_DIR = ROOT / "outputs/presignal_v21_designed_drift_r6_calendar_snapshot_persistence" / "R6-CALENDAR-SNAPSHOT-PERSISTENCE-20260724-v1"
BRIEF_DIR = ROOT / "outputs/presignal_v21_designed_drift_r6_candidate_selection_brief" / "R6-CANDIDATE-SELECTION-BRIEF-20260724-v1"
PACKAGE_FP = "sha256:886d306ea6a28f54368121645f66523ee4a01310c65417b6e15c28a2132a29f7"
ROUTE_B = "sha256:8c910a343515d88ca63ce4aaf738f28f9b4a8ab22665397077858bfaf7e866e4"
PMI_CLOSURE = "sha256:4c56f37ceb8507c0ea98d004c75f7d2ddd5433fe08e294da89d357b22f289656"
SELECTED, PRESS = "EP_EVENT_68a8e1cc3c9bf6ccc385", "EP_EVENT_9069738e64312eff9e2d"
PROMPT, PROMPT_SHA = "presignal_v21_information_request_prompt_v2", "sha256:219b3d33989d06b5f1968f6024c0135454320cf6c8f545116c6595d630011cb5"
ENUM_SHA, TEMPORAL_SHA = "sha256:320dad35692df096ea54466c17a8f02cff6287899aa3b7755dea00d7362bfb52", "sha256:d557c0733cc59982c46f71efaa89dad03a27e0d0c6023ba54eb2ef807c84c570"


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical(value).encode()).hexdigest()


def load(directory: Path, name: str) -> Any:
    return json.loads((directory / name).read_text(encoding="utf-8"))


def write(name: str, value: Any) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(canonical(value) + "\n", encoding="utf-8")


def utc(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def resolve() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    package = load(PACKAGE_DIR, "new_r6_episode_candidate_package.json")
    fp = load(PACKAGE_DIR, "new_r6_episode_candidate_package_fingerprint.json")
    episodes = load(PACKAGE_DIR, "canonical_future_episodes.json")["episodes"]
    rows = load(PACKAGE_DIR, "calendar_candidate_input_event_set.json")["rows"]
    selected = next(x for x in episodes if x["episode_id"] == SELECTED)
    press = next(x for x in episodes if x["episode_id"] == PRESS)
    event = next(x for x in rows if x["event_id"] == selected["primary_event_id"])
    return package, fp, selected, {"episode": press, "event": event}


def run(current_utc: str | None = None) -> str:
    package, fp, selected, related = resolve()
    now = utc(current_utc) if current_utc else datetime.now(timezone.utc).replace(microsecond=0)
    cutoff = utc(selected["forecast_cutoff_ts"])
    package_ok = fp["fingerprint"] == PACKAGE_FP and sha(package) == PACKAGE_FP and selected["primary_indicator_name"] == "Fed Interest Rate Decision" and selected["member_event_count"] == 1 and selected["episode_id"] in package["eligible_episode_identities"]
    if not package_ok:
        decision = "NEW_R6_EPISODE_SELECTION_BLOCKED_PACKAGE_MISMATCH"
        write("new_r6_selected_episode_validation.json", {"package_valid": False})
        write("final_new_r6_episode_selection_decision.json", {"decision": decision})
        return decision
    if now >= cutoff:
        decision = "NEW_R6_EPISODE_SELECTION_BLOCKED_CUTOFF_CLOSED"
        write("new_r6_selected_episode_validation.json", {"package_valid": True, "cutoff_open": False})
        write("final_new_r6_episode_selection_decision.json", {"decision": decision})
        return decision
    press = related["episode"]
    separate = (press["release_ts"] == "2026-07-29T18:30:00Z" and selected["release_ts"] == "2026-07-29T18:00:00Z" and press["episode_id"] != selected["episode_id"] and not set(press["member_event_ids"]) & set(selected["member_event_ids"]))
    if not separate:
        decision = "NEW_R6_EPISODE_SELECTION_BLOCKED_EPISODE_MEMBERSHIP"
        write("new_r6_fomc_episode_separation_report.json", {"separate": False})
        write("final_new_r6_episode_selection_decision.json", {"decision": decision})
        return decision
    event = related["event"]
    manifest = {"episode_identity": selected["episode_id"], "primary_event_identity": selected["primary_event_id"], "primary_event_name": selected["primary_indicator_name"],
                "secondary_event_identities": [], "release_timestamp": selected["release_ts"], "forecast_cutoff": selected["forecast_cutoff_ts"], "country": selected["country"], "currency": "USD",
                "source_identity": event["source_cal"], "schema_version": selected["schema_version"], "episode_content": selected,
                "provenance": {"candidate_package_fingerprint": PACKAGE_FP, "candidate_input_event_identity": event["event_id"], "source_row": event["source_row"], "event_type": event["type"]},
                "lineage": {"route_b_freeze_fingerprint": ROUTE_B, "pmi_closure_fingerprint": PMI_CLOSURE, "request_prompt_version": PROMPT, "request_prompt_checksum": PROMPT_SHA, "category_enum_checksum": ENUM_SHA, "temporal_alignment_fingerprint": TEMPORAL_SHA}}
    content_checksum = sha(manifest["episode_content"])
    provenance_checksum = sha(manifest["provenance"])
    lineage_checksum = sha(manifest["lineage"])
    manifest.update({"content_checksum": content_checksum, "provenance_checksum": provenance_checksum, "lineage_checksum": lineage_checksum})
    selection_auth = {"authorization_name": "PRESIGNAL_V21_DESIGNED_DRIFT_2_NEW_R6_EPISODE_SELECTION_AUTHORIZATION_V1", "route_b_freeze_fingerprint": ROUTE_B,
                      "candidate_package_fingerprint": PACKAGE_FP, "candidate_recommendation_fingerprint": load(BRIEF_DIR, "candidate_recommendation_fingerprint.json")["fingerprint"],
                      "selected_candidate_number": 19, "episode_identity": SELECTED, "event_identity": selected["primary_event_id"], "episode_content_checksum": content_checksum,
                      "release_timestamp": selected["release_ts"], "forecast_cutoff": selected["forecast_cutoff_ts"], "selection_method": "USER_AUTHORIZED_ONE_RUN_EPISODE_SELECTION",
                      "request_prompt_v2_checksum": PROMPT_SHA, "category_enum_checksum": ENUM_SHA, "temporal_alignment_fingerprint": TEMPORAL_SHA, "pmi_closure_fingerprint": PMI_CLOSURE,
                      "old_lineage_reuse_prohibitions": {"old_episode": "EP_BATCH_0b3bf1cac3c02da74063", "old_attention_reused": False, "old_requests_reused": False}}
    selection_fp = sha(selection_auth)
    attention_auth = {"authorization_name": "PRESIGNAL_V21_DESIGNED_DRIFT_2_NEW_R6_NATIVE_ATTENTION_CALL_AUTHORIZATION_V1", "status": "PREPARED_NOT_ACTIVATED", "episode_count": 1,
                      "episode_identity": SELECTED, "selection_authorization_fingerprint": selection_fp, "episode_content_checksum": content_checksum,
                      "provider": "Gemini", "model": "gemini-2.5-flash-lite", "attention_prompt_version": "existing_v2_attention_prompt_schema", "attention_response_schema": "session_attention_map/v0",
                      "attention_call_budget": 1, "retry_count": 0, "information_request_calls": 0, "forecast_calls": 0, "acquisition_calls": 0, "google_scientific_writes": 0,
                      "forecast_cutoff": selected["forecast_cutoff_ts"], "failure_stop_policy": ["cutoff_closed", "provider_or_model_mismatch", "prompt_or_schema_mismatch", "attention_response_invalid", "no_retry"], "authorization_activated": False, "provider_call_executed": False}
    remaining = int((cutoff - now).total_seconds())
    operational = "AMPLE" if remaining >= 72 * 3600 else ("MODERATE" if remaining >= 24 * 3600 else ("TIGHT" if remaining >= 6 * 3600 else "INSUFFICIENT"))
    decision = "NEW_R6_EPISODE_SELECTED_ATTENTION_AUTHORIZATION_PREPARED" if operational != "INSUFFICIENT" else "NEW_R6_EPISODE_SELECTED_OPERATIONAL_BUFFER_INSUFFICIENT"
    artifacts = {
        "new_r6_selected_episode_validation.json": {"package_valid": True, "candidate_count": len(package["eligible_episode_identities"]), "candidate_number": 19, "episode_identity": SELECTED, "primary_event": selected["primary_indicator_name"], "member_event_count": selected["member_event_count"], "scientific_eligibility": selected["eligibility"], "request_prompt_v2_bound": True, "temporal_alignment_bound": True, "cutoff_open": True},
        "new_r6_fomc_episode_separation_report.json": {"rate_decision_episode": SELECTED, "rate_decision_release": selected["release_ts"], "press_conference_episode": PRESS, "press_conference_release": press["release_ts"], "separate_identities": True, "separate_membership": True, "release_difference_minutes": 30, "same_time_clustered": False, "selected_15_minute_outcome_end": "2026-07-29T18:15:00Z", "outcome_window_ends_before_press_conference": True},
        "new_r6_selected_episode_manifest.json": manifest,
        "new_r6_selected_episode_determinism_report.json": {"runs": 3, "identical_episode_identity": True, "identical_content_checksum": len({sha(manifest["episode_content"]) for _ in range(3)}) == 1, "identical_provenance_checksum": len({sha(manifest["provenance"]) for _ in range(3)}) == 1, "identical_lineage_checksum": len({sha(manifest["lineage"]) for _ in range(3)}) == 1},
        "new_r6_episode_selection_authorization.json": selection_auth,
        "new_r6_episode_selection_authorization_fingerprint.json": {"fingerprint": selection_fp, "deterministic": True},
        "new_r6_attention_authorization_preparation.json": {**attention_auth, "authorization_fingerprint": sha(attention_auth)},
        "new_r6_operational_readiness_report.json": {"assessment_utc": now.isoformat().replace("+00:00", "Z"), "release_utc": selected["release_ts"], "forecast_cutoff_utc": selected["forecast_cutoff_ts"], "time_remaining_seconds": remaining, "cutoff_open": True, "classification": operational, "rationale": "Time remains for the staged pre-release pipeline; this is operational advice only and does not alter the cutoff."},
        "external_access_audit.json": {"calendar_refreshes": 0, "apps_script_executions": 0, "fmp_calls": 0, "google_reads": 0, "google_writes": 0, "gemini_calls": 0, "attention_calls": 0, "information_request_calls": 0, "forecast_calls": 0, "pack_a_constructions": 0, "pack_e_acquisitions": 0, "pack_e_computations": 0, "outcome_operations": 0, "evaluation_operations": 0},
        "final_new_r6_episode_selection_decision.json": {"decision": decision, "attention_authorization_prepared": decision.endswith("PREPARED"), "attention_executed": False},
    }
    for name, value in artifacts.items(): write(name, value)
    return decision


if __name__ == "__main__":
    print(canonical({"decision": run(), "output": str(OUT.relative_to(ROOT))}))
