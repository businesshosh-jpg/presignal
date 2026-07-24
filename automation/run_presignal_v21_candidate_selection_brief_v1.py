"""Advisory-only presentation of the committed R6 candidate package."""
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

OUT = ROOT / "outputs/presignal_v21_designed_drift_r6_candidate_selection_brief" / "R6-CANDIDATE-SELECTION-BRIEF-20260724-v1"
SOURCE = ROOT / "outputs/presignal_v21_designed_drift_r6_calendar_snapshot_persistence" / "R6-CALENDAR-SNAPSHOT-PERSISTENCE-20260724-v1"
PACKAGE_FP = "sha256:886d306ea6a28f54368121645f66523ee4a01310c65417b6e15c28a2132a29f7"
ROUTE_B = "sha256:8c910a343515d88ca63ce4aaf738f28f9b4a8ab22665397077858bfaf7e866e4"
PROMPT = "presignal_v21_information_request_prompt_v2"
PROMPT_SHA = "sha256:219b3d33989d06b5f1968f6024c0135454320cf6c8f545116c6595d630011cb5"
ENUM_SHA = "sha256:320dad35692df096ea54466c17a8f02cff6287899aa3b7755dea00d7362bfb52"
TEMPORAL_SHA = "sha256:d557c0733cc59982c46f71efaa89dad03a27e0d0c6023ba54eb2ef807c84c570"


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical(value).encode()).hexdigest()


def load(name: str) -> Any:
    return json.loads((SOURCE / name).read_text(encoding="utf-8"))


def write(name: str, value: Any) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(canonical(value) + "\n", encoding="utf-8")


def utc(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def relevance(name: str) -> tuple[str, str]:
    text = name.lower()
    if any(x in text for x in ("fed interest rate", "fed press", "gdp", "pce price", "personal spending", "durable goods", "consumer confidence")):
        return "HIGH", "Direct US monetary-policy, growth, or inflation transmission to Treasury yields and USD/JPY."
    if any(x in text for x in ("chicago pmi", "dallas fed", "new home", "case-shiller", "jobless", "employment")):
        return "MEDIUM", "Relevant US growth or labor signal with an indirect USD/JPY channel."
    return "LOW", "Limited direct linkage to US monetary-policy expectations or USD/JPY."


def complexity(episode: dict[str, Any]) -> str:
    count = int(episode["member_event_count"])
    if count >= 8:
        return "HIGH"
    if count >= 3:
        return "MODERATE"
    return "LOW"


def cluster(episode: dict[str, Any]) -> str:
    count = int(episode["member_event_count"])
    if count == 1:
        return "SINGLE_EVENT"
    if count <= 4:
        return "COHERENT_SAME_TIME_CLUSTER"
    return "LARGE_MIXED_BATCH"


def run(current_utc: str | None = None) -> str:
    package, fp = load("new_r6_episode_candidate_package.json"), load("new_r6_episode_candidate_package_fingerprint.json")
    episode_report = load("episode_eligibility_report.json")
    episodes = episode_report["eligible"]
    current = utc(current_utc) if current_utc else datetime.now(timezone.utc).replace(microsecond=0)
    valid = fp["fingerprint"] == PACKAGE_FP and sha(package) == PACKAGE_FP and len(episodes) == 29
    if not valid:
        decision = "NEW_R6_CANDIDATE_SELECTION_BRIEF_BLOCKED_PACKAGE_MISMATCH"
        write("candidate_package_validation.json", {"package_valid": False, "observed_fingerprint": fp.get("fingerprint"), "expected_fingerprint": PACKAGE_FP})
        write("final_candidate_selection_brief_decision.json", {"decision": decision})
        return decision
    rows = []
    for number, episode in enumerate(episodes, 1):
        cutoff = utc(episode["forecast_cutoff_ts"])
        status = "CURRENTLY_OPEN" if current < cutoff else "CURRENTLY_EXPIRED"
        rel, rationale = relevance(episode["primary_indicator_name"])
        comp, kind = complexity(episode), cluster(episode)
        remaining = max(0, int((cutoff - current).total_seconds()))
        suitability = "UNUSABLE" if status == "CURRENTLY_EXPIRED" else ("WEAK" if remaining < 12 * 3600 else ("STRONG" if rel == "HIGH" and comp != "HIGH" else "ACCEPTABLE"))
        rows.append({"candidate_number": number, "episode_identity": episode["episode_id"], "primary_event": episode["primary_indicator_name"],
                     "secondary_events": [x for x in episode["member_indicator_names"] if x != episode["primary_indicator_name"]],
                     "release_utc": episode["release_ts"], "forecast_cutoff_utc": episode["forecast_cutoff_ts"],
                     "package_time_remaining_seconds": int((cutoff - utc(episode_report["reference_utc"])).total_seconds()), "current_cutoff_status": status,
                     "current_time_remaining_seconds": remaining, "event_count": episode["member_event_count"], "cluster_type": kind,
                     "usdjpy_relevance": rel, "relevance_rationale": rationale, "acquisition_complexity": comp, "operational_suitability": suitability})
    open_rows = [r for r in rows if r["current_cutoff_status"] == "CURRENTLY_OPEN"]
    # Categorical, nonauthoritative operational preference; this never selects.
    preferred = ["EP_EVENT_68a8e1cc3c9bf6ccc385", "EP_BATCH_1b2be219c9f590b82eb6", "EP_BATCH_63e4c0657f864822a37f", "EP_EVENT_87ba5afa51d860207d38", "EP_BATCH_8f83521f91716206a5f3"]
    shortlist = []
    for rank, ident in enumerate(preferred, 1):
        row = next((r for r in open_rows if r["episode_identity"] == ident), None)
        if row:
            warning = "Large mixed release batch creates broad acquisition scope." if row["acquisition_complexity"] == "HIGH" else "Pre-release source availability still needs later validation."
            shortlist.append({"rank": rank, **row, "main_strength": row["relevance_rationale"], "main_warning": warning})
    recommended = shortlist[0] if shortlist else None
    decision = "NEW_R6_CANDIDATE_SELECTION_BRIEF_READY_USER_DECISION_REQUIRED" if recommended else "NEW_R6_CANDIDATE_PACKAGE_EXPIRED_REFRESH_REQUIRED"
    validation = {"candidate_package_fingerprint": fp["fingerprint"], "package_valid": True, "route_b_freeze_fingerprint": ROUTE_B,
                  "current_source_event_set_checksum": package["current_source_event_set_checksum"], "candidate_input_event_set_checksum": package["candidate_input_event_set_checksum"],
                  "episode_set_checksum": package["canonical_episode_set_checksum"], "eligible_candidate_count": len(episodes), "closed_pmi_excluded": True,
                  "request_prompt_v2_bound": package["request_prompt_version"] == PROMPT and package["request_prompt_checksum"] == PROMPT_SHA,
                  "temporal_alignment_bound": package["request_temporal_alignment_fingerprint"] == TEMPORAL_SHA}
    recommendation_basis = {"candidate_package_fingerprint": fp["fingerprint"], "frozen_reference_timestamp": episode_report["reference_utc"],
                            "all_candidate_identities": [r["episode_identity"] for r in rows], "shortlisted_candidate_identities": [r["episode_identity"] for r in shortlist],
                            "recommended_candidate_identity": recommended["episode_identity"] if recommended else None,
                            "recommendation_rationale": "Open cutoff, ample time, direct Fed-policy relevance, standalone scope, and clear later outcome boundary." if recommended else "No currently open candidate.",
                            "request_prompt_version": PROMPT, "request_prompt_checksum": PROMPT_SHA, "category_enum_checksum": ENUM_SHA,
                            "temporal_alignment_fingerprint": TEMPORAL_SHA, "recommendation_advisory": True, "selection_authorization_created": False}
    artifacts = {
        "candidate_package_validation.json": validation,
        "all_eligible_episode_decision_table.json": {"rows": rows, "ordering": "committed eligible Episode order"},
        "candidate_current_cutoff_status.json": {"assessment_utc": current.isoformat().replace("+00:00", "Z"), "open_count": len(open_rows), "closed_count": len(rows) - len(open_rows), "rows": [{k: r[k] for k in ("candidate_number", "episode_identity", "current_cutoff_status", "current_time_remaining_seconds")} for r in rows]},
        "candidate_usdjpy_relevance_assessment.json": {"rows": [{k: r[k] for k in ("candidate_number", "episode_identity", "usdjpy_relevance", "relevance_rationale")} for r in rows]},
        "candidate_acquisition_complexity_assessment.json": {"rows": [{k: r[k] for k in ("candidate_number", "episode_identity", "event_count", "acquisition_complexity")} for r in rows]},
        "candidate_operational_suitability.json": {"rows": [{k: r[k] for k in ("candidate_number", "episode_identity", "current_cutoff_status", "operational_suitability")} for r in rows]},
        "candidate_shortlist.json": {"shortlist": shortlist, "nonauthoritative_operational_summary": True},
        "candidate_recommendation.json": {"assessment_utc": current.isoformat().replace("+00:00", "Z"), **recommendation_basis, "recommended_candidate": recommended},
        "candidate_recommendation_fingerprint.json": {"fingerprint": sha(recommendation_basis), "assessment_timestamp_excluded": True},
        "external_access_audit.json": {"calendar_refresh_calls": 0, "apps_script_executions": 0, "fmp_calls": 0, "google_reads": 0, "google_writes": 0, "gemini_calls": 0, "attention_calls": 0, "information_request_calls": 0, "forecast_calls": 0, "pack_a_constructions": 0, "pack_e_acquisitions": 0, "pack_e_computations": 0, "r6_evidence_writes": 0, "outcome_operations": 0, "evaluation_operations": 0},
        "final_candidate_selection_brief_decision.json": {"decision": decision, "selection_authorization_created": False},
    }
    for name, value in artifacts.items(): write(name, value)
    report = ["# New R6 Candidate Selection Brief", "", "Advisory only. No Episode selection authorization was created.", "", "## Recommendation", "", f"Recommend candidate {recommended['candidate_number']}: `{recommended['episode_identity']}` — {recommended['primary_event']}." if recommended else "No currently open candidate.", "", "## Shortlist", ""]
    report += [f"- {x['rank']}. {x['primary_event']} (`{x['episode_identity']}`): {x['main_strength']} Warning: {x['main_warning']}" for x in shortlist]
    (OUT / "new_r6_candidate_selection_brief.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    return decision


if __name__ == "__main__":
    print(canonical({"decision": run(), "output": str(OUT.relative_to(ROOT))}))
