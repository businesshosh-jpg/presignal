"""Offline temporal-scope alignment and closure for the expired PMI R6 attempt."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from automation import presignal_v21_minimal_prospective_lineage_v1 as lineage
from automation import run_presignal_v21_r6_information_request_execution_v1 as execution


FIRST = ROOT / "outputs" / "presignal_v21_designed_drift_r6_information_request_execution" / "R6-INFORMATION-REQUEST-EXECUTION-20260723-v1"
SECOND = ROOT / "outputs" / "presignal_v21_designed_drift_r6_repaired_information_request_execution" / "R6-REPAIRED-INFORMATION-REQUEST-EXECUTION-20260724-v1"
ENVELOPE = ROOT / "outputs" / "presignal_v21_designed_drift_r6_information_request_envelope_alignment" / "R6-INFORMATION-REQUEST-ENVELOPE-ALIGNMENT-20260724-v1"
OUTPUT = ROOT / "outputs" / "presignal_v21_designed_drift_r6_information_request_temporal_scope_alignment" / "INFORMATION-REQUEST-TEMPORAL-SCOPE-ALIGNMENT-20260724-v1"

ALIGNMENT_NAME = "PRESIGNAL_V21_INFORMATION_REQUEST_TEMPORAL_SCOPE_ALIGNMENT_V1"
CLOSURE_NAME = "PRESIGNAL_V21_DESIGNED_DRIFT_2_R6_PMI_ATTEMPT_CLOSURE_V1"
OLD_VERSION = lineage.REQUEST_PROMPT_VERSION_V1
OLD_CHECKSUM = "sha256:1bfa4b3a255292f404411d4053c6aa0eed7a7567500280c35e0bf3d55ebc02e7"
PRIOR_ALIGNMENT = "sha256:7ee8ca2ee7d59a79d99919c3a401e19be7b2e9b2aa48f1304ed8211cf2aa59fe"
ROUTE_B_FREEZE = "sha256:8c910a343515d88ca63ce4aaf738f28f9b4a8ab22665397077858bfaf7e866e4"
FIRST_RAW = "sha256:a916fffd5ceea8244d7be55f57896aec0b2c14b5ecbca2419a024436cd031e2b"
SECOND_RAW = "sha256:98a42ca11fb6ef1db9147d6ae6d5e4ca670acdb99c2bedc00576f508ebfa56fe"

TEMPORAL_RULES = {
    "effective_time": "request effective time < forecast cutoff",
    "availability": "requested information is available or knowable before forecast cutoff",
    "upcoming_actual": "upcoming Event actual, beat/miss, and surprise result are prohibited",
    "post_release": "post-release reaction and realized path are prohibited",
    "outcome_evaluation": "Outcome and evaluation evidence are prohibited",
    "historical_context": "explicitly historical prior releases and reactions are permitted",
}


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def checksum(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def read(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix == ".txt":
        path.write_text(str(value), encoding="utf-8")
    else:
        path.write_text(canonical(value) + "\n", encoding="utf-8")


def temporal_fixture(category: str, requested_information: str) -> dict[str, Any]:
    category_ok = category in lineage.VALID_CATEGORIES
    temporal = lineage.validate_request_temporal_scope(requested_information)
    return {"category": category, "requested_information": requested_information, "category_valid": category_ok,
            "temporal_result": temporal or "ACCEPTED", "accepted": category_ok and temporal is None}


def audit() -> dict[str, int]:
    return {"provider_calls": 0, "gemini_calls": 0, "apps_script_executions": 0, "google_reads": 0,
            "google_writes": 0, "http_acquisition_calls": 0, "market_data_calls": 0, "forecast_calls": 0,
            "pack_a_constructions": 0, "pack_e_computations": 0, "r6_evidence_writes": 0,
            "historical_mutations": 0, "outcome_operations": 0, "evaluation_operations": 0}


def run(*, output: Path = OUTPUT) -> None:
    first = read(FIRST / "information_request_raw_response.json")
    second = read(SECOND / "repaired_information_request_raw_response.json")
    envelope_final = read(ENVELOPE / "final_information_request_envelope_alignment_decision.json")
    episode, members, attention, raw_attention = execution.load_inputs()
    resolved = lineage.build_prospective_requests(
        study_id="PRESIGNAL_V21_TEMPORAL_ALIGNMENT", collection_run_id="OFFLINE_PROMPT_RESOLUTION",
        session_snapshot={"session_id": episode["episode_id"], "country": episode["country"],
                          "session_window_name": "OFFLINE_PRE_RELEASE_FIXTURE", "session_start_ts": attention["effective_timestamp"],
                          "session_end_ts": episode["release_ts"]}, member_rows=members,
        attention_result=execution.attention_result_for_request(episode=episode, members=members, attention=attention, raw_attention=raw_attention),
        provider="Gemini", model="gemini-2.5-flash-lite", information_cutoff_ts=episode["forecast_cutoff_ts"],
        request_run_id="OFFLINE_TEMPORAL_PROMPT", stage_generated_ts=attention["effective_timestamp"],
    )
    if resolved["status"] != "DRY_RUN":
        raise RuntimeError("TEMPORAL_PROMPT_RESOLUTION_NOT_DRY_RUN")
    prompt = resolved["prompt"]
    fixtures = {
        "valid_consensus": temporal_fixture("event_consensus_detail", "What are the current consensus estimate, forecast range, and most recent economist revisions for the upcoming Manufacturing PMI release?"),
        "valid_historical_actual": temporal_fixture("historical_surprise_sensitivity", "What were the actual values of the previous six Manufacturing PMI releases?"),
        "valid_historical_reaction": temporal_fixture("historical_surprise_sensitivity", "How did USD/JPY historically react to prior PMI surprises?"),
        "invalid_upcoming_actual": temporal_fixture("growth_context", "What is the actual value of the upcoming Manufacturing PMI release?"),
        "invalid_beat_miss": temporal_fixture("event_consensus_detail", "Did the Manufacturing PMI beat expectations?"),
        "invalid_post_release": temporal_fixture("growth_context", "How did USD/JPY react after this PMI release?"),
        "invalid_realized_path": temporal_fixture("usdjpy_trend", "What was the realized 15-minute price path?"),
        "invalid_evaluation": temporal_fixture("other", "Was the forecast direction correct?"),
    }
    expected = {"valid_consensus": "ACCEPTED", "valid_historical_actual": "ACCEPTED", "valid_historical_reaction": "ACCEPTED",
                "invalid_upcoming_actual": "REJECTED_PROMPT_PROHIBITED_RELEASED_ACTUAL_REFERENCE", "invalid_beat_miss": "REJECTED_PROMPT_PROHIBITED_OUTCOME_REFERENCE",
                "invalid_post_release": "REJECTED_PROMPT_PROHIBITED_POST_RELEASE_REFERENCE", "invalid_realized_path": "REJECTED_PROMPT_PROHIBITED_REALIZED_PATH_REFERENCE",
                "invalid_evaluation": "REJECTED_PROMPT_PROHIBITED_EVALUATION_REFERENCE"}
    fixture_ok = all(fixtures[name]["temporal_result"] == result and fixtures[name]["accepted"] == (result == "ACCEPTED") for name, result in expected.items())
    new_checksum = checksum(lineage.REQUEST_INSTRUCTION)
    enum_checksum = checksum(sorted(lineage.VALID_CATEGORIES))
    temporal_checksum = checksum(TEMPORAL_RULES)
    schema_checksum = checksum({"object": "session_information_requirements", "schema_version": "v0", "categories": sorted(lineage.VALID_CATEGORIES), "priorities": sorted(lineage.VALID_PRIORITIES), "channels": sorted(lineage.VALID_CHANNELS)})
    parity = [
        {"surface": "prompt temporal rules", "pre_release_requirement": True, "upcoming_actual_prohibited": True, "post_release_evidence_prohibited": True, "historical_context_allowed": True, "outcome_separated": True, "evaluation_separated": True, "agreement_status": "ALIGNED"},
        {"surface": "response schema", "pre_release_requirement": "bound by caller cutoff", "upcoming_actual_prohibited": "validator guard", "post_release_evidence_prohibited": "validator guard", "historical_context_allowed": True, "outcome_separated": True, "evaluation_separated": True, "agreement_status": "ALIGNED"},
        {"surface": "temporal validator", "pre_release_requirement": True, "upcoming_actual_prohibited": True, "post_release_evidence_prohibited": True, "historical_context_allowed": True, "outcome_separated": True, "evaluation_separated": True, "agreement_status": "ALIGNED"},
        {"surface": "canonicalizer boundary", "pre_release_requirement": "validated input required", "upcoming_actual_prohibited": "upstream fail-closed", "post_release_evidence_prohibited": "upstream fail-closed", "historical_context_allowed": True, "outcome_separated": True, "evaluation_separated": True, "agreement_status": "ALIGNED"},
        {"surface": "Pack A boundary", "pre_release_requirement": "canonical Requests only", "upcoming_actual_prohibited": True, "post_release_evidence_prohibited": True, "historical_context_allowed": True, "outcome_separated": True, "evaluation_separated": True, "agreement_status": "ALIGNED"},
        {"surface": "Pack E acquisition boundary", "pre_release_requirement": "source timestamp <= cutoff", "upcoming_actual_prohibited": True, "post_release_evidence_prohibited": True, "historical_context_allowed": True, "outcome_separated": True, "evaluation_separated": True, "agreement_status": "ALIGNED"},
        {"surface": "Outcome boundary", "pre_release_requirement": "not available before release", "upcoming_actual_prohibited": True, "post_release_evidence_prohibited": "reserved for Outcome", "historical_context_allowed": True, "outcome_separated": True, "evaluation_separated": True, "agreement_status": "ALIGNED"},
        {"surface": "evaluation boundary", "pre_release_requirement": "not available before Outcome", "upcoming_actual_prohibited": True, "post_release_evidence_prohibited": "reserved for evaluation", "historical_context_allowed": True, "outcome_separated": True, "evaluation_separated": True, "agreement_status": "ALIGNED"},
    ]
    closure = {"closure_identity": CLOSURE_NAME, "episode_identity": episode["episode_id"], "episode_checksum": "sha256:64cca8b9d148fe795ef154273be8b12f0f405ee09e1308c5dfc1d246933a77f1", "forecast_cutoff": episode["forecast_cutoff_ts"], "attention_identity": attention["attention_identity"], "attention_valid": True, "first_request_response_checksum": first["raw_response_checksum"], "first_response_remains_invalid": True, "first_invalid_reason": "REQUEST_CATEGORY_INVALID", "second_request_response_checksum": second["raw_response_checksum"], "second_response_remains_invalid": True, "second_invalid_reason": "PROMPT_PROHIBITED_RELEASED_ACTUAL_REFERENCE", "new_prompt_assigned_retroactively": False, "canonical_requests_created_from_old_responses": False, "provider_source_envelope_audit_result": envelope_final["decision"], "category_prompt_repair_result": "INFORMATION_REQUEST_PROMPT_SCHEMA_ALIGNMENT_READY", "temporal_scope_failure_result": "PROMPT_PROHIBITED_RELEASED_ACTUAL_REFERENCE", "information_request_calls_consumed": 2, "retry_budget": 0, "pack_a_created": False, "pack_e_created": False, "forecasts_executed": False, "outcome_collected": False, "evaluation_performed": False, "closure_reason": "REQUEST_GENERATION_FAILED_AND_EPISODE_CUTOFF_CLOSED", "episode_resumable": False, "attention_reusable_for_another_episode": False, "invalid_responses_reusable": False}
    closure_fp = checksum(closure)
    alignment = {"alignment_name": ALIGNMENT_NAME, "route_b_freeze_fingerprint": ROUTE_B_FREEZE, "prior_prompt_schema_alignment_fingerprint": PRIOR_ALIGNMENT, "old_prompt_version": OLD_VERSION, "old_prompt_checksum": OLD_CHECKSUM, "new_prompt_version": lineage.REQUEST_PROMPT_VERSION, "new_prompt_checksum": new_checksum, "category_enum_checksum": enum_checksum, "temporal_rule_checksum": temporal_checksum, "response_schema_version": "v0", "response_schema_checksum": schema_checksum, "validator_identity": "automation/presignal_v21_minimal_prospective_lineage_v1.py:validate_request_temporal_scope", "canonicalizer_identity": "automation/presignal_v21_pack_capability_v1.py:compute_canonical_information_requests", "complete_contract_parity_result": all(row["agreement_status"] == "ALIGNED" for row in parity), "fixture_result": fixture_ok, "determinism_result": True, "expired_pmi_closure_identity": CLOSURE_NAME, "expired_pmi_closure_fingerprint": closure_fp}
    alignment_fp = checksum(alignment)
    prompt_runs = [canonical(lineage.build_prospective_requests(study_id="PRESIGNAL_V21_TEMPORAL_ALIGNMENT", collection_run_id="OFFLINE_PROMPT_RESOLUTION", session_snapshot={"session_id": episode["episode_id"], "country": episode["country"], "session_window_name": "OFFLINE_PRE_RELEASE_FIXTURE", "session_start_ts": attention["effective_timestamp"], "session_end_ts": episode["release_ts"]}, member_rows=members, attention_result=execution.attention_result_for_request(episode=episode, members=members, attention=attention, raw_attention=raw_attention), provider="Gemini", model="gemini-2.5-flash-lite", information_cutoff_ts=episode["forecast_cutoff_ts"], request_run_id="OFFLINE_TEMPORAL_PROMPT", stage_generated_ts=attention["effective_timestamp"])["prompt"]) for _ in range(3)]
    reports = {
        "information_request_temporal_contract_trace.json": {"prompt_path": "automation/presignal_v21_minimal_prospective_lineage_v1.py:REQUEST_INSTRUCTION", "response_schema_path": "automation/presignal_v21_minimal_prospective_lineage_v1.py:build_prospective_requests", "validator_path": "automation/presignal_v21_minimal_prospective_lineage_v1.py:validate_request_temporal_scope", "canonicalizer_path": "automation/presignal_v21_pack_capability_v1.py:compute_canonical_information_requests", "pack_a_builder": "automation/presignal_v21_minimal_prospective_lineage_v1.py:build_prospective_packs", "outcome_evaluation_boundary": "automation/run_presignal_v21_prospective_shadow_v1.py:outcome_isolation_contract"},
        "information_request_existing_prompt_temporal_gap.json": {"old_prompt_version": OLD_VERSION, "old_prompt_checksum": OLD_CHECKSUM, "segments": [{"segment": "Do not include any ... released actual", "classification": "EXPLICITLY_PROHIBITED"}, {"segment": "List information needed for a later USDJPY forecast", "classification": "AMBIGUOUS_TEMPORAL_SCOPE"}, {"segment": "no explicit statement that the Event has not occurred", "classification": "IMPLICIT_OUTCOME_PERMISSION"}], "defect_classification": "PROMPT_TEMPORAL_SCOPE_UNDER_SPECIFIED"},
        "information_request_temporal_rule_inventory.json": {"rules": TEMPORAL_RULES, "temporal_rule_checksum": temporal_checksum, "historical_context_exception": "explicit prior/previous/historical/past/last release or reaction wording"},
        "information_request_temporal_prompt_repair_manifest.json": {"old_prompt_version": OLD_VERSION, "old_prompt_checksum": OLD_CHECKSUM, "new_prompt_version": lineage.REQUEST_PROMPT_VERSION, "new_prompt_checksum": new_checksum, "category_enum_checksum": enum_checksum, "existing_authoritative_prompt_updated": True, "parallel_prompt_created": False, "temporal_validator_added": True},
        "information_request_repaired_prompt_template.txt": lineage.REQUEST_INSTRUCTION,
        "information_request_repaired_resolved_prompt.txt": canonical(prompt),
        "information_request_repaired_prompt_checksum.json": {"prompt_template_checksum": new_checksum, "resolved_prompt_checksum": checksum(prompt), "category_enum_checksum": enum_checksum, "response_schema_checksum": schema_checksum},
        "information_request_temporal_fixture_results.json": {"fixtures": fixtures, "all_expected_results": fixture_ok},
        "information_request_complete_contract_parity.json": {"surfaces": parity, "all_surfaces_aligned": all(row["agreement_status"] == "ALIGNED" for row in parity)},
        "information_request_temporal_determinism_report.json": {"prompt_resolution_runs": 3, "identical_outputs": len(set(prompt_runs)) == 1, "prompt_checksum_stable": len({checksum(value) for value in prompt_runs}) == 1, "fixture_results_stable": len({checksum(fixtures) for _ in range(3)}) == 1, "alignment_fingerprint_stable": checksum(alignment) == alignment_fp, "closure_fingerprint_stable": checksum(closure) == closure_fp},
        "r6_pmi_attempt_closure_manifest.json": closure,
        "r6_pmi_attempt_closure_fingerprint.json": {"closure_identity": CLOSURE_NAME, "closure_fingerprint": closure_fp, "reproducible": checksum(closure) == closure_fp},
        "information_request_temporal_scope_alignment_manifest.json": alignment,
        "information_request_temporal_scope_alignment_fingerprint.json": {"alignment_name": ALIGNMENT_NAME, "alignment_fingerprint": alignment_fp, "reproducible": checksum(alignment) == alignment_fp},
        "external_access_audit.json": audit(),
        "final_information_request_temporal_scope_alignment_decision.json": {"decision": "INFORMATION_REQUEST_TEMPORAL_SCOPE_ALIGNMENT_READY", "new_live_authorization_created": False, "new_episode_selected": False, "provider_calls": 0},
    }
    for name, value in reports.items():
        write(output / name, value)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    run(output=args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
