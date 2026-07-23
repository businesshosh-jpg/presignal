"""Emit deterministic R6 Episode-selection evidence for an explicit user choice."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))
from automation import presignal_v21_r6_episode_selection_v1 as selection

REFRESH = ROOT / "outputs/presignal_v21_designed_drift_r6_episode_refresh/R6-EPISODE-REFRESH-20260723-v1"
OUT = ROOT / "outputs/presignal_v21_designed_drift_r6_episode_selection/R6-EPISODE-SELECTION-AUTHORIZATION-20260723-v1"
REFRESH_COMMIT = "85a6a622c7b535a41a9da77226a2f47f4b14f83e"


def write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True); path.write_text(selection.canonical(value) + "\n", encoding="utf-8")


def reports(*, authorization_time_utc: str, candidate_number: int | None = None, selected_episode_id: str | None = None) -> dict[str, Any]:
    candidate = json.loads((REFRESH / "next_r6_episode_candidate.json").read_text())
    episodes = json.loads((REFRESH / "canonical_episode_inventory.json").read_text())
    eligibility = json.loads((REFRESH / "episode_eligibility_report.json").read_text())
    readback = json.loads((REFRESH / "google_event_readback_report.json").read_text())
    final = json.loads((REFRESH / "final_episode_refresh_decision.json").read_text())
    manifest = json.loads((REFRESH / "prospective_event_refresh_manifest.json").read_text())
    candidates = candidate["eligible_candidates"]
    selection.validate_inventory(candidates=candidates, episode_checksum=selection.checksum(episodes["episodes"]), expected_episode_checksum=manifest["canonical_episode_checksum"], readback_valid=bool(readback["identity_semantics_valid"]))
    revalidation = selection.cutoff_revalidation(candidates, authorization_time_utc=authorization_time_utc)
    # Candidate objects carry immutable member names in the same canonical order.
    comparison = []
    for number, item in enumerate(candidates, 1):
        secondaries = [{"event_id": event_id, "event_name": name} for event_id, name in zip(item["member_event_ids"], item["member_indicator_names"]) if event_id != item["primary_event_id"]]
        comparison.append({"candidate_number": number, "episode_identity": item["episode_id"], "primary_event_identity": item["primary_event_id"], "primary_event_name": item["primary_indicator_name"], "secondary_events": secondaries, "event_count": item["member_event_count"], "release_time_utc": item["release_ts"], "forecast_cutoff_utc": item["forecast_cutoff_ts"], "country": item["country"], "market_session_context": item["market_session_context"], "source_lineage": item["member_event_ids"], "schema_version": item["schema_version"], "eligibility_status": item["eligibility"]})
    evidence_checksum = selection.checksum({"manifest": manifest, "candidate": candidate, "episodes": episodes, "eligibility": eligibility, "readback": readback, "final": final})
    inventory_checksum = selection.checksum(candidates)
    any_open = any(row["cutoff_currently_open"] for row in revalidation)
    decision = "R6_EPISODE_SELECTION_AWAITING_EXPLICIT_CANDIDATE" if any_open else "R6_EPISODE_SELECTION_AUTHORIZATION_NO_OPEN_CANDIDATE"
    waiting = {"selection_status": "AWAITING_EXPLICIT_USER_SELECTION" if any_open else "NO_OPEN_CANDIDATE", "selection_method": selection.SELECTION_METHOD, "explicit_candidate_supplied": False, "selected_candidate_number": None, "selected_episode_identity": None, "permanent_tie_break_introduced": False, "one_run_only": True}
    user_authority: dict[str, Any] = waiting
    authorization_manifest: dict[str, Any] = {"status": "NOT_CREATED_AWAITING_EXPLICIT_USER_SELECTION", "authorization_name": selection.AUTHORIZATION_NAME}
    authorization_fingerprint: dict[str, Any] = {"status": "NOT_CREATED_AWAITING_EXPLICIT_USER_SELECTION", "waiting_decision_fingerprint": selection.checksum({"decision": decision, "candidate_inventory_checksum": inventory_checksum, "selection_method": selection.SELECTION_METHOD}), "selected_authorization_fingerprint": None}
    final_reason = "No explicit Episode identity was supplied by the user; no candidate was selected or ranked."
    if candidate_number is not None or selected_episode_id is not None:
        if not any_open:
            decision = "R6_EPISODE_SELECTION_AUTHORIZATION_NO_OPEN_CANDIDATE"
            final_reason = "The explicitly selected Episode cannot be bound because its forecast cutoff has passed."
        else:
            bound = selection.bind_explicit_selection(candidates=candidates, candidate_number=candidate_number or 0, selected_episode_id=selected_episode_id, authorization_time_utc=authorization_time_utc, refresh_commit=REFRESH_COMMIT, refresh_evidence_checksum=evidence_checksum, candidate_inventory_checksum=inventory_checksum)
            decision = "R6_EPISODE_SELECTED_NATIVE_ATTENTION_EXECUTION_READY"
            final_reason = "Candidate was explicitly authorized by the user for one Gemini Attention call only."
            user_authority = {"selection_status": "EXPLICIT_USER_SELECTION_BOUND", "selection_method": selection.SELECTION_METHOD, "explicit_candidate_supplied": True, "selected_candidate_number": candidate_number, "selected_episode_identity": selected_episode_id, "permanent_tie_break_introduced": False, "one_run_only": True}
            authorization_manifest = bound["manifest"]
            authorization_fingerprint = {"authorization_name": selection.AUTHORIZATION_NAME, "authorization_fingerprint": bound["fingerprint"], "hash_algorithm": "SHA-256", "canonicalization": "sorted-key compact UTF-8 JSON"}
    return {"episode_selection_candidate_inventory.json": {"candidate_count": len(candidates), "candidates": candidates, "candidate_inventory_checksum": inventory_checksum, "refresh_evidence_checksum": evidence_checksum, "frozen_eligibility_valid": True, "readback_valid": True}, "episode_selection_candidate_comparison.json": {"comparison": comparison, "informational_only": ["time until cutoff", "time until release", "cluster size"], "permanent_ranking": False}, "episode_selection_cutoff_revalidation.json": {"authorization_time_utc": authorization_time_utc, "candidates": revalidation}, "episode_selection_user_authority.json": user_authority, "episode_selection_authorization_manifest.json": authorization_manifest, "episode_selection_authorization_fingerprint.json": authorization_fingerprint, "authorization_preservation_report.json": {"route_b_freeze_fingerprint": selection.ROUTE_B_FREEZE, "r6_authorization_v3_fingerprint": selection.R6_V3, "native_attention_authorization_fingerprint": selection.NATIVE_ATTENTION_AUTH, "all_valid": True, "attention_calls_performed": 0, "attention_calls_remaining": 1, "retry_budget": 0}, "external_access_audit.json": {"google_episode_reads": 0, "google_writes": 0, "gemini_attention_calls": 0, "other_provider_calls": 0, "forecast_calls": 0, "acquisition_calls": 0, "r6_evidence_writes": 0, "outcome_operations": 0, "evaluation_operations": 0}, "final_episode_selection_decision.json": {"decision": decision, "reason": final_reason, "candidate_inventory_checksum": inventory_checksum, "attention_call_budget_remaining": 1}}


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--authorization-time-utc", required=True); parser.add_argument("--candidate-number", type=int); parser.add_argument("--selected-episode-id"); parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args(); values = reports(authorization_time_utc=args.authorization_time_utc)
    if args.candidate_number is not None or args.selected_episode_id is not None:
        values = reports(authorization_time_utc=args.authorization_time_utc, candidate_number=args.candidate_number, selected_episode_id=args.selected_episode_id)
    for name, value in values.items(): write(args.output / name, value)
    return 0


if __name__ == "__main__": raise SystemExit(main())
