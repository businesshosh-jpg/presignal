#!/usr/bin/env python3
"""Freeze the local-only confirmatory prospective Round 2 protocol."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "outputs" / "presignal_v21_full_round_1_forecast_execution"
OUTPUT_DIR = BASE / "PPHB-R2-CONFIRMATORY-PROSPECTIVE-PROTOCOL-20260804T080000Z"
PROTOCOL_ID = "PPHB-R2-CONFIRMATORY-PROSPECTIVE-PROTOCOL-20260804T080000Z"
AGGREGATE_DIR = BASE / "PPHB-R1-ROUND-1-AGGREGATE-EVALUATION-RESULT-20260804T050000Z"
FINAL_REPORT_DIR = BASE / "PPHB-R1-ROUND-1-FINAL-REPORT-20260804T060000Z"
INFERENCE_DIR = BASE / "PPHB-R1-PAIRED-T15-INFERENCE-RESULT-20260804T070000Z"
INFERENCE_AUTH = BASE / "PPHB-R1-PAIRED-T15-INFERENCE-20260804T070000Z" / "inference_authorization.json"
PROVIDER_MODELS = (
    {"provider": "Anthropic", "model": "claude-haiku-4-5"},
    {"provider": "Gemini", "model": "gemini-2.5-flash-lite"},
    {"provider": "OpenAI", "model": "gpt-4o-mini-2024-07-18"},
)
SIX_METRICS = (
    "T+15 directional accuracy",
    "Immediate Impulse directional accuracy",
    "magnitude interval error (pips)",
    "horizon accuracy",
    "path accuracy",
    "reversal accuracy",
)


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def file_digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def accepted_artifact_bindings() -> dict[str, dict[str, str]]:
    paths = {
        "aggregate_result": (AGGREGATE_DIR.name, AGGREGATE_DIR / "aggregate_metrics.json"),
        "final_report": (FINAL_REPORT_DIR.name, FINAL_REPORT_DIR / "scientific_interpretation.json"),
        "paired_inference_authorization": ("PPHB-R1-PAIRED-T15-INFERENCE-AUTHORIZATION-20260804T070000Z", INFERENCE_AUTH),
        "paired_inference_result": (INFERENCE_DIR.name, INFERENCE_DIR / "paired_t15_inference.json"),
    }
    return {name: {"artifact_id": artifact_id, "sha256": file_digest(path)} for name, (artifact_id, path) in paths.items()}


def build_protocol() -> dict[str, Any]:
    return {
        "protocol_id": PROTOCOL_ID,
        "protocol_schema_version": "1.0.0",
        "protocol_status": "FROZEN_EXECUTION_NOT_AUTHORIZED",
        "decision": "PROSPECTIVE_ROUND_2_PROTOCOL_FROZEN",
        "preparation_readiness": "PROSPECTIVE_ROUND_2_EXECUTION_PREPARATION_READY",
        "accepted_round_1_bindings": accepted_artifact_bindings(),
        "accepted_round_1_conclusion": {
            "historical_period": "May-July 2024",
            "pack_a_role": "baseline",
            "pack_e_role": "hypothesis-supported experimental arm",
            "evidence_strength": "MODERATE_DESCRIPTIVE_EVIDENCE_WITHOUT_INFERENTIAL_SUPPORT",
            "paired_t15_four_cell_table": {
                "both_correct": 46,
                "pack_a_correct_pack_e_incorrect": 40,
                "pack_a_incorrect_pack_e_correct": 54,
                "both_incorrect": 66,
            },
            "exact_two_sided_mcnemar_p_value": 0.17966501480803043,
            "round_1_conclusion_boundary": "Round 1 did not establish Pack E superiority, Pack A replacement, provider selection, or a future-performance guarantee.",
        },
        "round_2_purpose_and_hypothesis": {
            "purpose": "Prospectively confirm or fail to confirm a Pack E versus Pack A difference in T+15 directional accuracy while separately measuring coverage and no-signal behavior.",
            "null_hypothesis": "Among common paired-scoreable prospective observations, Pack A-correct/Pack E-incorrect and Pack A-incorrect/Pack E-correct discordant outcomes are equally likely.",
            "alternative_hypothesis": "Among common paired-scoreable prospective observations, the discordant outcome probabilities differ between Pack A and Pack E.",
            "arms": {"pack_a": "baseline", "pack_e": "experimental"},
            "not_a_provider_selection_or_meta_forecast_study": True,
        },
        "prospective_boundary": {
            "round_2_start_condition": "Begin only after this protocol is accepted, a future study envelope and the first Round 2 Slice manifest are frozen, and one explicit execution authorization is accepted before any provider dispatch.",
            "episode_eligibility": "A unique authoritative scheduled event Episode with authoritative USD/JPY instrument binding, exact release timestamp, deterministic cutoff, complete paired Pack lineage, and no prior Round 2 identity use.",
            "event_and_instrument_authority": "Use the existing v2.1 authoritative event identity and USD/JPY instrument binding; reject uncertain event, release-time, cutoff, or instrument identity.",
            "release_and_cutoff_rule": "information_cutoff_ts <= prompt_freeze_ts < forecast_freeze_deadline_ts < release_ts; all Pack A/E shared inputs and prompt fingerprints freeze at or before the cutoff, and both forecast calls complete before release.",
            "historical_leakage_prevention": "Every Episode, provider/model allocation, Pack input, prompt fingerprint, forecast identity, and Outcome identity must be frozen before dispatch and before the Outcome is available. Released actuals, post-cutoff facts, and Outcome observations are prohibited from forecast inputs.",
            "forecast_identity": "Use the existing canonical v2.1 forecast call identity bound to Episode, provider, model, Pack, cutoff, prompt fingerprint, and immutable manifest lineage.",
            "outcome_identity": "Use the existing canonical Outcome identity under presignal_event_path_contract_v1_1 and schema 2.1.1, bound to Episode, USD/JPY, release timestamp, measurement windows, source authority, and append-only lineage.",
            "append_only_evidence": ["frozen manifest", "authorization", "provider request and raw response evidence", "forecast validation evidence", "Outcome evidence", "attachment reconciliation", "minimal evaluation", "final Round 2 reconciliation"],
        },
        "provider_model_control": {
            "permitted_provider_models": list(PROVIDER_MODELS),
            "allocation_rule": "For every admitted Episode, pre-enumerate one Pack A and one Pack E call for each permitted provider/model route in the frozen manifest. Both arms share the same Episode, provider, model, cutoff, release timestamp, measurement windows, and Outcome identity; only the accepted Pack content differs.",
            "authority": "Existing prospective v2.1 provider/model control and paired prompt contract.",
            "prohibitions": ["provider selection based on Round 1", "outcome-informed reallocation", "silent provider/model substitution", "post-outcome provider/model replacement"],
            "replacement_rule": "A provider/model replacement or allocation change requires a separate explicit authorization before the affected manifest is frozen.",
        },
        "primary_endpoint": {
            "name": "T+15 directional accuracy",
            "primary": True,
            "forecast_labels": ["UP", "DOWN", "FLAT", "NO_SIGNAL"],
            "scoreability": "A directional forecast is scoreable only when its accepted T+15 label is UP, DOWN, or FLAT, the attached Outcome is valid, and the canonical evaluator returns boolean T+15 correctness. NO_SIGNAL is not correct or incorrect and is excluded from the directional denominator.",
            "flat_treatment": "FLAT is a directional endpoint label and is correct only when the accepted Outcome direction is FLAT under the existing canonical tie rule.",
            "pack_specific_denominator": "Each Pack denominator is its accepted valid, attached, scoreable T+15 forecasts after NO_SIGNAL, unavailable Outcome, terminal-invalid, and authority exclusions.",
            "common_paired_scoreable_population": "Direct Pack A/E comparison uses only matching same-Episode/provider/model pairs where both Pack A and Pack E are T+15 scoreable against the same attached Outcome.",
            "unavailable_outcome_treatment": "Preserve source evidence and apply only the existing symmetric paired-exclusion rule when its prerequisites are satisfied; otherwise stop for separate governance. Never impute, interpolate, or substitute an Outcome.",
            "tie_and_rounding": "Both-correct and both-incorrect pairs are retained in reporting and omitted from the McNemar statistic. Store exact values; display proportions and risk differences to six decimals.",
        },
        "coverage_and_no_signal_plan": {
            "separate_descriptive_reports": ["total eligible Episodes", "valid forecast records", "valid attached Outcome records", "directional coverage by Pack", "NO_SIGNAL count and rate by Pack", "T+15 directional accuracy conditional on scoreability by Pack", "common paired-scoreable T+15 count", "unavailable and paired-excluded Episode count"],
            "directional_coverage_definition": "Accepted directional UP/DOWN/FLAT forecasts divided by accepted valid forecasts with an attached valid Outcome, reported separately by Pack.",
            "no_signal_definition": "Accepted forecast marked NO_SIGNAL divided by accepted valid forecasts with an attached valid Outcome, reported separately by Pack.",
            "comparison_boundary": "Different Pack-specific coverage and directional denominators are descriptive. Direct accuracy comparison uses only the common paired-scoreable population.",
            "prohibitions": ["treating NO_SIGNAL as automatically correct", "treating NO_SIGNAL as automatically incorrect", "coverage-adjusted composite scoring", "post-outcome no-signal recoding"],
        },
        "inferential_plan": {
            "test": "Exact two-sided McNemar binomial test",
            "endpoint": "T+15 directional accuracy only",
            "population": "Final Round 2 common paired-scoreable observations only",
            "discordant_pairs": ["Pack A correct / Pack E incorrect", "Pack A incorrect / Pack E correct"],
            "alpha": 0.05,
            "calculation": "Two times the lower exact binomial tail under p=0.5, capped at 1.0; no continuity correction.",
            "ties": "Both-correct and both-incorrect pairs do not enter the test statistic and remain in the four-cell table.",
            "missing_data": "No unavailable, terminal-invalid, authority-excluded, NO_SIGNAL, or non-scoreable record enters the common paired-scoreable test population.",
            "confidence_interval": "Not reported: no canonical paired risk-difference interval method and confidence level are governed.",
            "interim_analysis": "Prohibited. Operational completeness counts may be checked for safe execution, but no cumulative Pack comparison, efficacy/futility analysis, or inferential calculation occurs before final Round 2 lock.",
            "interpretation_boundary": "A result concerns the frozen Round 2 paired population only and does not establish causality, universal superiority, provider selection validity, Pack A replacement, or future performance guarantees.",
        },
        "secondary_metric_boundary": {
            "authorized_descriptive_metrics": list(SIX_METRICS[1:]),
            "immediate_impulse": "Secondary only; report strict directional accuracy only for Outcomes marked SUPPORTED by the existing contract. Do not convert APPROXIMATION_ONLY Outcomes into strict scores.",
            "other_metrics": "Magnitude/pip error, horizon accuracy, path accuracy, and reversal accuracy remain descriptive and use the existing canonical evaluator, denominators, tie, and rounding rules.",
            "not_authorized": ["composite score", "provider-level inference", "subgroup inference", "multiple-comparison adjustment", "Bayesian analysis", "post-hoc threshold selection"],
        },
        "sample_size_and_stopping_design": {
            "design_type": "Bounded operational scenario design; not a post-hoc power calculation and not a guarantee of future effect or availability.",
            "round_1_operational_reference": {"available_outcomes": 138, "unavailable_paired_exclusions": 10, "evaluated_pairs": 259, "common_paired_scoreable_pairs": 206, "pack_a_no_signal": 51, "pack_e_no_signal": 7, "discordant_pairs": 94},
            "target_eligible_episodes": 120,
            "maximum_eligible_episodes": 144,
            "target_common_paired_scoreable_observations": 240,
            "minimum_common_paired_scoreable_observations_for_confirmatory_test": 200,
            "scenario_table": [
                {"eligible_episodes": 96, "planned_provider_episode_pairs": 288, "planning_only_expected_common_pairs": "approximately 214"},
                {"eligible_episodes": 120, "planned_provider_episode_pairs": 360, "planning_only_expected_common_pairs": "approximately 267"},
                {"eligible_episodes": 144, "planned_provider_episode_pairs": 432, "planning_only_expected_common_pairs": "approximately 320"},
            ],
            "stopping_rule": "Accrue in deterministic frozen Slices through 120 eligible Episodes. If the final locked 120-Episode cohort has fewer than 240 common paired-scoreable observations, continue only with additional whole deterministic Slices up to 144 eligible Episodes. Stop recruitment at the first completed cohort meeting 240 common pairs or at 144 Episodes, whichever comes first.",
            "insufficient_population_rule": "If the 144-Episode ceiling closes below 200 common paired-scoreable observations, preserve all evidence and do not run the confirmatory test; require a separate authorization for any further interpretation or extension.",
            "unavailable_rule": "Unavailable Outcomes are preserved. Symmetric paired exclusion is permitted only under the existing accepted rule; it does not replace the minimum common-pair requirement.",
        },
        "execution_cadence": {
            "canonical_outcome_controller": "automation/run_presignal_v21_authorized_slice.py",
            "forecast_path": "Existing v2.1 canonical forecast execution path; no new Round 2 forecast runner is created by this protocol.",
            "per_slice_pattern": "One frozen manifest, one explicit end-to-end authorization, and one coherent Codex execution session. Collection, attachment, and minimal evaluation advance only after accepted append-only evidence.",
            "maximum_episodes_per_slice": 48,
            "apps_script_ceiling": "One read per distinct UTC release day in the frozen Slice manifest.",
            "market_data_ceiling": "One authorized collection attempt per selected Episode.",
            "total_request_ceiling": "Exact sum of the manifest-derived Apps Script and market-data ceilings.",
            "default_limits": {"google_writes": 0, "retries": 0, "local_attachment_records": "At most the selected eligible Episode count"},
            "mechanical_repair_boundary": "The accepted prospective-slice execution contract permits only deterministic interface repairs that preserve values, hashes, canonical ownership, and frozen ceilings; governance conflicts stop execution.",
            "round_2_completion": "After final locked Slice completion, reconcile all manifests, authorizations, outcomes, paired exclusions, attachments, evaluations, and common-scoreable identities before separately authorized final inference.",
        },
        "mandatory_governance_stops": [
            "identity, count, manifest, fingerprint, provider/model, cutoff, or Pack-lineage conflict",
            "historical leakage or Outcome availability before forecast freeze",
            "ambiguous artifact authority or remote state",
            "missing or contradictory Outcome semantics",
            "unsupported metric, denominator, confidence-interval method, or test substitution",
            "need for an unauthorized external request, retry, Google write, provider/model replacement, or alternate source",
            "any repair that changes forecast, Outcome, Pack, or metric meaning",
        ],
        "this_move_limits": {
            "round_2_execution": 0,
            "forecast_dispatches": 0,
            "provider_calls": 0,
            "apps_script_reads": 0,
            "market_data_requests": 0,
            "google_reads": 0,
            "google_writes": 0,
            "outcome_collection": 0,
            "outcome_attachment": 0,
            "metric_calculation": 0,
            "retries": 0,
        },
        "exact_next_move": "Prepare one separately authorized Round 2 execution envelope and its first prospective Slice manifest, including future Episode eligibility, pre-release cutoff verification, deterministic provider/model allocation, and per-Slice request ceilings; do not dispatch a forecast until that authorization is accepted.",
    }


def validate_protocol(protocol: dict[str, Any]) -> dict[str, Any]:
    fingerprint = protocol.get("protocol_fingerprint")
    unsigned = dict(protocol)
    unsigned.pop("protocol_fingerprint", None)
    if fingerprint is not None and fingerprint != digest(unsigned):
        raise ValueError("ROUND_2_PROTOCOL_FINGERPRINT_CONFLICT")
    if protocol["protocol_id"] != PROTOCOL_ID or protocol["protocol_status"] != "FROZEN_EXECUTION_NOT_AUTHORIZED":
        raise ValueError("ROUND_2_PROTOCOL_IDENTITY_CONFLICT")
    if protocol["accepted_round_1_bindings"] != accepted_artifact_bindings():
        raise ValueError("ROUND_2_ACCEPTED_ARTIFACT_BINDING_CONFLICT")
    if protocol["primary_endpoint"]["name"] != "T+15 directional accuracy" or not protocol["primary_endpoint"]["primary"]:
        raise ValueError("ROUND_2_PRIMARY_ENDPOINT_CONFLICT")
    if protocol["inferential_plan"]["test"] != "Exact two-sided McNemar binomial test" or protocol["inferential_plan"]["alpha"] != 0.05:
        raise ValueError("ROUND_2_INFERENCE_SPECIFICATION_CONFLICT")
    if tuple(protocol["provider_model_control"]["permitted_provider_models"]) != PROVIDER_MODELS:
        raise ValueError("ROUND_2_PROVIDER_MODEL_CONFLICT")
    sample = protocol["sample_size_and_stopping_design"]
    if (sample["target_eligible_episodes"], sample["maximum_eligible_episodes"], sample["target_common_paired_scoreable_observations"], sample["minimum_common_paired_scoreable_observations_for_confirmatory_test"]) != (120, 144, 240, 200):
        raise ValueError("ROUND_2_SAMPLE_DESIGN_CONFLICT")
    cadence = protocol["execution_cadence"]
    if cadence["maximum_episodes_per_slice"] != 48 or cadence["default_limits"] != {"google_writes": 0, "retries": 0, "local_attachment_records": "At most the selected eligible Episode count"}:
        raise ValueError("ROUND_2_CADENCE_CONFLICT")
    if any(value != 0 for value in protocol["this_move_limits"].values()):
        raise ValueError("ROUND_2_LOCAL_ONLY_LIMIT_CONFLICT")
    if set(protocol["secondary_metric_boundary"]["authorized_descriptive_metrics"]) != set(SIX_METRICS[1:]):
        raise ValueError("ROUND_2_SECONDARY_METRIC_CONFLICT")
    return {
        "decision": "PROSPECTIVE_ROUND_2_PROTOCOL_FROZEN",
        "preparation_readiness": "PROSPECTIVE_ROUND_2_EXECUTION_PREPARATION_READY",
        "protocol_id": protocol["protocol_id"],
        "protocol_fingerprint": fingerprint or digest(unsigned),
        "external_access": 0,
        "round_2_execution": 0,
        "metric_calculation": 0,
        "checks": ["Pack A/E separation", "T+15 primary hierarchy", "coverage and NO_SIGNAL definitions", "paired-scoreable population", "exact inferential specification", "provider/model control", "prospective leakage controls", "deterministic fingerprint"],
    }


def freeze(output_dir: Path) -> dict[str, Any]:
    if output_dir.exists():
        raise ValueError("ROUND_2_PROTOCOL_ARTIFACT_ALREADY_EXISTS")
    protocol = build_protocol()
    protocol["protocol_fingerprint"] = digest(protocol)
    validation = validate_protocol(protocol)
    output_dir.mkdir(parents=True)
    (output_dir / "round_2_protocol.json").write_text(json.dumps(protocol, indent=2, sort_keys=True) + "\n")
    (output_dir / "protocol_validation.json").write_text(json.dumps(validation, indent=2, sort_keys=True) + "\n")
    (output_dir / "protocol_decision.json").write_text(json.dumps({
        "decision": validation["decision"],
        "preparation_readiness": validation["preparation_readiness"],
        "protocol_id": PROTOCOL_ID,
        "protocol_fingerprint": protocol["protocol_fingerprint"],
        "external_access": 0,
        "round_2_execution": 0,
        "metrics_calculated": 0,
    }, indent=2, sort_keys=True) + "\n")
    return validation


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    args = parser.parse_args()
    result = freeze(args.output_dir)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
