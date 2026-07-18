#!/usr/bin/env python3
"""Freeze the value-blind Pack A/E evaluation contract and historical split."""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any, Iterable, Mapping


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "outputs/simplified_authoritative_replay"
DEFAULT_OUTPUT = ROOT / "docs/pack_ae_evaluation_contract_v1"
FROZEN_AT = "2026-07-18T17:31:28Z"
SOURCE_COMMIT = "6d7783c44d5f8c6974244ec656a3bc8d01b3726f"
READY_TAG = "presignal-v2-authoritative-evaluation-ready"
READY_ARCHIVE_SHA256 = "579cedcbaa204817cce2fc19af211f069fe99b09b53ae7e7a9030ca1e8b7bd09"
CONTRACT_ID = "PRESIGNAL-V2-PACK-AE-EVALUATION-CONTRACT-20260718T173128Z"
SPLIT_ID = "PRESIGNAL-V2-PACK-AE-HISTORICAL-SPLIT-20260718T173128Z"
AUDIT_ID = "PRESIGNAL-V2-PACK-AE-VALUE-BLINDNESS-AUDIT-20260718T173128Z"
PLAN_ID = "PRESIGNAL-V2-PACK-AE-IMPLEMENTATION-VALIDATION-PLAN-20260718T173128Z"
BINDING_ID = "PRESIGNAL-V2-PACK-AE-CONTRACT-BINDING-20260718T173128Z"
BOOTSTRAP_SEED = 20260718
BOOTSTRAP_RESAMPLES = 10_000
PROVIDERS = ("Anthropic", "Gemini", "OpenAI")

PACKAGE = BASE / "production_packages/SIMPLIFIED-REPLAY-PROD-20260718T010455Z"
RUN = BASE / "runs/SIMPLIFIED-REPLAY-AUTHORITATIVE-20260718T010455Z"
READY = BASE / "evaluation_readiness/SIMPLIFIED-REPLAY-EVALUATION-READINESS-RECOVERED-20260718T162600Z"
ATTACHMENT = BASE / "outcome_attachments/SIMPLIFIED-REPLAY-OUTCOME-ATTACHMENT-RECOVERED-20260718T162300Z"
OLD_ATTACHMENT = BASE / "outcome_attachments/SIMPLIFIED-REPLAY-OUTCOME-ATTACHMENT-20260718T103650Z"
CHECKPOINTS = BASE / "checkpoints"


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha256_value(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def read_jsonl_projection(path: Path, allowed_fields: Iterable[str]) -> list[dict[str, Any]]:
    allowed = tuple(allowed_fields)
    projected = []
    for line in path.read_text().splitlines():
        if not line:
            continue
        source = json.loads(line)
        projected.append({field: source.get(field) for field in allowed})
    return projected


def with_fingerprint(payload: Mapping[str, Any]) -> dict[str, Any]:
    artifact = dict(payload)
    artifact["fingerprint_algorithm"] = "SHA-256"
    artifact["fingerprint_scope"] = "canonical JSON of this artifact with artifact_fingerprint omitted"
    artifact["artifact_fingerprint"] = sha256_value(artifact)
    return artifact


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n")


def verify_frozen_state() -> dict[str, Any]:
    branch = subprocess.check_output(["git", "branch", "--show-current"], cwd=ROOT, text=True).strip()
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    tag_target = subprocess.check_output(["git", "rev-parse", READY_TAG + "^{}"], cwd=ROOT, text=True).strip()
    source_is_ancestor = subprocess.run(
        ["git", "merge-base", "--is-ancestor", SOURCE_COMMIT, head],
        cwd=ROOT,
        check=False,
    ).returncode == 0
    if branch != "codex-simplified-authoritative-replay" or not source_is_ancestor or tag_target != SOURCE_COMMIT:
        raise RuntimeError("FROZEN_SOURCE_STATE_MISMATCH")
    archive = CHECKPOINTS / "PRESIGNAL_V2_AUTHORITATIVE_EVALUATION_READY_20260718.tar.gz"
    if sha256_file(archive) != READY_ARCHIVE_SHA256:
        raise RuntimeError("EVALUATION_READY_ARCHIVE_MISMATCH")
    run = read_json(RUN / "run_manifest.json")
    ready = read_json(READY / "evaluation_readiness_summary.json")
    if run["binding"]["execution_deployment_version"] != 79:
        raise RuntimeError("REPLAY_DEPLOYMENT_VERSION_MISMATCH")
    endpoint = read_json(
        BASE / "historical_market_data_endpoint_source_bindings/"
        "SIMPLIFIED-REPLAY-HISTORICAL-MARKET-DATA-ENDPOINT-SOURCE-BINDING-20260718T152126Z/"
        "endpoint_source_binding.json"
    )
    if endpoint["endpoint"]["deployment_version"] != 81:
        raise RuntimeError("ENDPOINT_DEPLOYMENT_VERSION_MISMATCH")
    expected = {
        "total_committed_predictions": 1406,
        "attached_predictions": 1145,
        "unique_independent_market_sessions": 195,
        "complete_ae_provider_session_pairs": 562,
        "incomplete_provider_session_pairs": 21,
        "sessions_complete_across_all_three_providers": 174,
        "sessions_with_one_or_two_complete_provider_pairs": 21,
        "governed_scientific_exclusion_predictions": 261,
        "unexpected_attachment_failures": 0,
    }
    for key, expected_value in expected.items():
        if ready.get(key) != expected_value:
            raise RuntimeError("EVALUATION_READY_COUNT_MISMATCH:" + key)
    return {
        "branch": branch,
        "source_commit": SOURCE_COMMIT,
        "ready_tag": READY_TAG,
        "ready_tag_target": tag_target,
        "evaluation_ready_archive_sha256": READY_ARCHIVE_SHA256,
        "replay_deployment_version": 79,
        "historical_endpoint_deployment_version": 81,
        "package_id": "SIMPLIFIED-REPLAY-PROD-20260718T010455Z",
        "package_fingerprint": run["binding"]["whole_package_fingerprint"],
        "run_id": "SIMPLIFIED-REPLAY-AUTHORITATIVE-20260718T010455Z",
        "run_binding_sha256": run["binding_sha256"],
        "attachment_id": ready["attachment_artifact_id"],
        "attachment_fingerprint": ready["attachment_artifact_fingerprint"],
        "readiness_id": ready["artifact_id"],
        "readiness_fingerprint": read_json(READY / "readiness_fingerprint.json")["whole_artifact_fingerprint"],
    }


def build_split() -> tuple[dict[str, Any], dict[str, dict[str, int]]]:
    session_rows = read_jsonl_projection(
        PACKAGE / "snapshot/authoritative_sessions.jsonl",
        ("session_id", "session_start_ts"),
    )
    session_start = {row["session_id"]: row["session_start_ts"] for row in session_rows}
    pair_rows = read_jsonl_projection(
        READY / "provider_session_pair_readiness.jsonl",
        ("session_id", "provider", "complete_ae_pair"),
    )
    pair_by_session: dict[str, dict[str, bool]] = collections.defaultdict(dict)
    for row in pair_rows:
        if row["provider"] not in PROVIDERS:
            raise RuntimeError("UNEXPECTED_PROVIDER")
        pair_by_session[row["session_id"]][row["provider"]] = row["complete_ae_pair"] is True
    evaluable = [session_id for session_id, coverage in pair_by_session.items() if any(coverage.values())]
    if len(evaluable) != 195 or any(session_id not in session_start for session_id in evaluable):
        raise RuntimeError("EVALUABLE_SESSION_RECONCILIATION_FAILED")
    ordered = sorted(evaluable, key=lambda session_id: (session_start[session_id], session_id))
    partition_by_session = {
        session_id: "HISTORICAL_DEVELOPMENT" if index < 130 else "HISTORICAL_CONFIRMATORY_HOLDOUT"
        for index, session_id in enumerate(ordered)
    }
    entries = []
    counts: dict[str, collections.Counter[str]] = {
        "HISTORICAL_DEVELOPMENT": collections.Counter(),
        "HISTORICAL_CONFIRMATORY_HOLDOUT": collections.Counter(),
    }
    for order_index, session_id in enumerate(ordered, start=1):
        partition = partition_by_session[session_id]
        coverage = {
            provider: ("COMPLETE_AE_PAIR" if pair_by_session[session_id].get(provider) else "INCOMPLETE_AE_PAIR")
            for provider in PROVIDERS
        }
        providers_complete = [provider for provider in PROVIDERS if coverage[provider] == "COMPLETE_AE_PAIR"]
        for provider in providers_complete:
            counts[partition][provider] += 1
        entry = {
            "order_index": order_index,
            "session_id": session_id,
            "evaluation_start_timestamp": session_start[session_id],
            "partition": partition,
            "complete_pair_count": len(providers_complete),
            "provider_coverage": coverage,
        }
        entry["session_record_sha256"] = sha256_value(entry)
        entries.append(entry)
    exclusions = read_jsonl_projection(
        ATTACHMENT / "governed_exclusion_ledger.jsonl",
        ("session_id", "attachment_status"),
    )
    governed_sessions = sorted({row["session_id"] for row in exclusions})
    if len(governed_sessions) != 44 or len(exclusions) != 261:
        raise RuntimeError("GOVERNED_EXCLUSION_RECONCILIATION_FAILED")
    summary = {
        partition: {
            "sessions": sum(entry["partition"] == partition for entry in entries),
            "complete_pairs": sum(counter.values()),
            "complete_pairs_by_provider": {provider: counter[provider] for provider in PROVIDERS},
        }
        for partition, counter in counts.items()
    }
    if summary["HISTORICAL_DEVELOPMENT"]["sessions"] != 130:
        raise RuntimeError("DEVELOPMENT_SPLIT_COUNT_MISMATCH")
    if summary["HISTORICAL_CONFIRMATORY_HOLDOUT"]["sessions"] != 65:
        raise RuntimeError("HOLDOUT_SPLIT_COUNT_MISMATCH")
    split = with_fingerprint({
        "artifact_id": SPLIT_ID,
        "artifact_type": "DETERMINISTIC_MARKET_SESSION_DEVELOPMENT_HOLDOUT_SPLIT",
        "frozen_at": FROZEN_AT,
        "ordering_rule": ["evaluation_start_timestamp ASC", "session_id ASC"],
        "assignment_rule": {
            "first_130_sessions": "HISTORICAL_DEVELOPMENT",
            "final_65_sessions": "HISTORICAL_CONFIRMATORY_HOLDOUT",
        },
        "statistical_unit": "MARKET_SESSION",
        "provider_pairs_never_split_across_partitions": True,
        "partition_summary": summary,
        "session_records": entries,
        "ordered_session_record_hash": sha256_value([entry["session_record_sha256"] for entry in entries]),
        "governed_exclusions": {
            "partition": "OUTSIDE_DEVELOPMENT_AND_HOLDOUT",
            "sessions": 44,
            "predictions": 261,
            "session_ids": governed_sessions,
            "session_ids_sha256": sha256_value(governed_sessions),
        },
        "source_files": {
            "authoritative_sessions.jsonl": sha256_file(PACKAGE / "snapshot/authoritative_sessions.jsonl"),
            "provider_session_pair_readiness.jsonl": sha256_file(READY / "provider_session_pair_readiness.jsonl"),
            "governed_exclusion_ledger.jsonl": sha256_file(ATTACHMENT / "governed_exclusion_ledger.jsonl"),
        },
        "performance_values_used": False,
    })
    return split, {partition: dict(counter) for partition, counter in counts.items()}


def build_contract(binding: Mapping[str, Any]) -> dict[str, Any]:
    forecast_schema = read_json(PACKAGE / "schema/reduced_provider_schema_reference.json")
    outcome_contract = read_json(OLD_ATTACHMENT / "source_contract_configuration.json")
    if forecast_schema["directions"] != ["DOWN", "FLAT", "NO_CLEAR_DIRECTION", "UP"]:
        raise RuntimeError("FORECAST_DIRECTION_VOCABULARY_MISMATCH")
    if forecast_schema["reaction_strengths"] != ["MODERATE", "STRONG", "WEAK"]:
        raise RuntimeError("FORECAST_STRENGTH_VOCABULARY_MISMATCH")
    if outcome_contract["strength_thresholds_pips"] != {
        "medium_below": 15, "strong_at_or_above": 15, "weak_below": 5,
    }:
        raise RuntimeError("CANONICAL_STRENGTH_THRESHOLDS_MISMATCH")
    return with_fingerprint({
        "artifact_id": CONTRACT_ID,
        "artifact_type": "VALUE_BLIND_PACK_AE_EVALUATION_CONTRACT",
        "contract_version": "presignal.pack_ae_evaluation_contract.v1",
        "frozen_at": FROZEN_AT,
        "scientific_question": "Does the shared request-driven Market-State Pack improve Market Session forecast performance compared with no Market-State Pack?",
        "scientific_status": {
            "classification": "RETROSPECTIVELY_ASSEMBLED_PRE_ANALYSIS_SPECIFIED_CONFIRMATION",
            "limitation": "The recovered historical population was generated leakage-safely, but this evaluation contract was frozen after outcomes became available and before Pack A/E performance was inspected or scored.",
            "not_an_original_preregistration": True,
            "future_prospective_replication_required": True,
        },
        "frozen_source_binding": dict(binding),
        "population": {
            "primary_partition": "HISTORICAL_CONFIRMATORY_HOLDOUT",
            "primary_partition_sessions": 65,
            "development_partition_sessions": 130,
            "include_all_complete_exact_ae_provider_session_pairs": True,
            "include_partial_provider_coverage_sessions": True,
            "exclude_incomplete_provider_session_pairs": True,
            "governed_exclusions_remain_excluded": True,
        },
        "primary_endpoint": {
            "name": "PAIRED_ACTION_VALUE_DIFFERENCE",
            "forecast_action_value": {
                "correct_actionable_forecast": 1,
                "incorrect_actionable_forecast": -1,
                "NO_CLEAR_DIRECTION": 0,
            },
            "actionable_directions": ["UP", "DOWN", "FLAT"],
            "pair_formula": "Pack_E_action_value - Pack_A_action_value",
            "allowed_pair_differences": [-2, -1, 0, 1, 2],
            "session_statistic": "arithmetic mean of all available complete provider-pair differences within the Market Session",
            "primary_effect": "arithmetic mean of the 65 holdout Market Session statistics",
            "pooled_pair_mean": "supporting estimate only",
        },
        "categorical_rules": {
            "NO_CLEAR_DIRECTION": "non-actionable; action value 0 regardless of canonical realized direction; excluded from actionable-accuracy denominator but included in pair action value and coverage",
            "FLAT": "actionable; +1 only when canonical realized direction is FLAT, otherwise -1",
            "UP": "actionable; +1 only when canonical realized direction is UP, otherwise -1",
            "DOWN": "actionable; +1 only when canonical realized direction is DOWN, otherwise -1",
        },
        "strength_normalization": {
            "forecast_vocabulary": ["WEAK", "MODERATE", "STRONG"],
            "canonical_vocabulary": ["WEAK", "MEDIUM", "STRONG"],
            "mapping": {"WEAK": "WEAK", "MODERATE": "MEDIUM", "STRONG": "STRONG"},
            "strength_accuracy": "exact equality after normalization; supporting metric only",
            "primary_decision_gate": False,
        },
        "statistical_unit": {
            "independent_unit": "MARKET_SESSION",
            "provider_pairs_within_session": "clustered and averaged before primary inference",
            "provider_weighting": "no post-hoc weighting; each available provider pair contributes equally within its session",
        },
        "uncertainty": {
            "method": "DETERMINISTIC_MARKET_SESSION_CLUSTER_BOOTSTRAP",
            "seed": BOOTSTRAP_SEED,
            "resamples": BOOTSTRAP_RESAMPLES,
            "resampling_unit": "MARKET_SESSION",
            "sample_size_per_resample": 65,
            "resampling_algorithm": "Python random.Random(seed).randrange(N), repeated N times per resample; selected sessions retain all available complete provider pairs; repeated sessions contribute repeatedly",
            "statistic": "mean of sampled Market Session mean pair differences",
            "interval": "two-sided 95% percentile interval",
            "percentiles": [0.025, 0.975],
            "quantile_algorithm": "Type 7 linear interpolation: h=(B-1)*p, interpolate sorted bootstrap estimates at floor(h) and ceil(h)",
        },
        "decision_rule": {
            "PACK_E_IMPROVES_FORECASTING": "holdout mean session-level difference > 0 and 95% interval lower bound > 0",
            "PACK_E_UNDERPERFORMS_PACK_A": "holdout mean session-level difference < 0 and 95% interval upper bound < 0",
            "INSUFFICIENT_EVIDENCE_OF_PACK_E_IMPROVEMENT": "all other outcomes; must not be interpreted as equivalence",
            "supporting_analyses_cannot_override_primary": True,
        },
        "secondary_metrics": {
            "actionable_directional_accuracy": "correct actionable forecasts divided by UP/DOWN/FLAT forecasts; report coverage beside accuracy",
            "actionable_forecast_coverage": "UP/DOWN/FLAT forecasts divided by all forecasts",
            "NO_CLEAR_DIRECTION_rate": "NO_CLEAR_DIRECTION forecasts divided by all forecasts",
            "A_wrong_E_correct": "pairs with A action value -1 and E action value +1",
            "A_correct_E_wrong": "pairs with A action value +1 and E action value -1",
            "provider_specific_action_value_difference": "mean pair difference for each provider with same session-cluster bootstrap; supporting only",
            "sessions_unanimously_favoring_A": "every available provider pair difference in the session is strictly below zero",
            "sessions_unanimously_favoring_E": "every available provider pair difference in the session is strictly above zero",
            "sessions_with_mixed_provider_effects": "at least one provider pair difference above zero and at least one below zero",
            "neutral_or_nonunanimous_session_reconciliation": "sessions containing zero differences that satisfy none of the three effect categories; reconciliation only",
            "complete_three_provider_robustness": "repeat primary statistic and bootstrap on holdout sessions with all three complete pairs; cannot override primary",
            "strength_accuracy": "exact normalized strength accuracy by arm and paired difference; supporting only",
            "forecast_completeness": "descriptive attachment/readiness counts only; not a performance endpoint",
        },
        "overall_accuracy": {
            "status": "NOT_DEFINED_FOR_REDUCED_REPLAY",
            "legacy_overall_ok_used": False,
            "new_composite_created": False,
        },
        "confidence_calibration": {
            "status": "DEFERRED_TO_PROSPECTIVE_CALIBRATION",
            "decision_gate": False,
            "historical_descriptive_analysis_allowed_under_this_contract": False,
        },
        "missing_data": {
            "incomplete_ae_pair": "excluded from paired performance metrics and retained in completeness reconciliation",
            "missing_required_direction_or_strength_in_complete_pair": "UNEXPECTED_EVALUATION_FAILURE; do not impute or silently drop",
            "missing_canonical_outcome_for_attached_pair": "INTEGRITY_FAILURE; stop evaluation",
            "valid_partial_provider_session": "included using all available complete provider pairs",
        },
        "development_partition": {
            "permitted_uses": [
                "verify scoring implementation",
                "validate category normalization",
                "test artifact construction",
                "identify software defects",
            ],
            "prohibited_uses": [
                "revise the primary metric after results are viewed",
                "revise the holdout decision rule after results are viewed",
                "tune Pack E",
                "select providers or sessions based on results",
            ],
        },
        "holdout_access": {
            "open_exactly_once": True,
            "allowed_only_after": [
                "contract commit and tag are verified",
                "development-only implementation validation passes without contract change",
                "scoring implementation hash is frozen",
            ],
            "contract_revision_after_development_results": "requires a new untouched prospective population; the historical holdout must not be evaluated under the revised contract",
        },
        "prohibited_post_hoc_changes": [
            "change primary endpoint",
            "change action values or category treatment",
            "change split or exclusions",
            "change bootstrap seed, resample count, interval, or quantile method",
            "change decision thresholds",
            "remove valid pairs or reweight providers",
            "promote a supporting metric over the primary result",
        ],
        "schema_sources": {
            "reduced_provider_schema_sha256": sha256_file(PACKAGE / "schema/reduced_provider_schema_reference.json"),
            "outcome_contract_configuration_sha256": sha256_file(OLD_ATTACHMENT / "source_contract_configuration.json"),
        },
        "performance_values_used_to_construct_contract": False,
    })


def build_value_blindness_audit(binding: Mapping[str, Any]) -> dict[str, Any]:
    return with_fingerprint({
        "artifact_id": AUDIT_ID,
        "artifact_type": "VALUE_BLINDNESS_AUDIT",
        "frozen_at": FROZEN_AT,
        "result": "PASS_VALUE_BLIND",
        "performance_scoring_accessed": False,
        "arm_correctness_accessed": False,
        "pair_score_differences_accessed": False,
        "provider_win_rates_accessed": False,
        "outcome_conditioned_arm_behavior_accessed": False,
        "allowed_inputs_read": [
            {"file": "authoritative_sessions.jsonl", "fields": ["session_id", "session_start_ts"]},
            {"file": "provider_session_pair_readiness.jsonl", "fields": ["session_id", "provider", "complete_ae_pair"]},
            {"file": "governed_exclusion_ledger.jsonl", "fields": ["session_id", "attachment_status"]},
            {"file": "evaluation_readiness_summary.json", "fields": ["population and missingness counts", "artifact bindings"]},
            {"file": "reduced_provider_schema_reference.json", "fields": ["allowed directions", "allowed strengths", "required fields"]},
            {"file": "source_contract_configuration.json", "fields": ["outcome thresholds", "window and lineage contract"]},
            {"file": "checkpoint and Git metadata", "fields": ["identities", "fingerprints", "commit", "tag", "deployment versions"]},
        ],
        "prohibited_inputs_not_read": [
            "Pack A or Pack E correctness",
            "arm-level action values",
            "pair-level score differences",
            "provider performance summaries",
            "outcome-conditioned arm behavior",
            "development or holdout performance values",
        ],
        "construction_constraint": "All discretionary rules were supplied by the value-blind freeze request or were exact semantic vocabulary normalization; no observed performance informed them.",
        "frozen_source_binding": dict(binding),
    })


def build_validation_plan() -> dict[str, Any]:
    return with_fingerprint({
        "artifact_id": PLAN_ID,
        "artifact_type": "IMPLEMENTATION_VALIDATION_PLAN",
        "frozen_at": FROZEN_AT,
        "contract_id": CONTRACT_ID,
        "split_id": SPLIT_ID,
        "sequence": [
            "verify frozen contract commit and tag",
            "implement scoring from contract constants without reading holdout values",
            "unit-test all direction action values and strength normalization",
            "unit-test session clustering, bootstrap reproducibility, Type 7 percentiles, and decision boundaries with synthetic fixtures",
            "run scoring only on HISTORICAL_DEVELOPMENT",
            "validate development artifact construction and reconcile software failures",
            "freeze scoring implementation hash without changing contract",
            "verify holdout access gate",
            "open HISTORICAL_CONFIRMATORY_HOLDOUT exactly once",
        ],
        "development_only_checks": [
            "pair selection matches split manifest",
            "category normalization is exhaustive",
            "NO_CLEAR_DIRECTION and FLAT rules match contract",
            "session means do not weight sessions by provider count",
            "bootstrap is deterministic at seed 20260718 for 10000 resamples",
            "all output component hashes reproduce",
        ],
        "synthetic_boundary_tests": [
            "each allowed pair difference -2,-1,0,1,2",
            "decision interval entirely above zero",
            "decision interval entirely below zero",
            "interval touching zero",
            "mean equal to zero",
            "partial provider coverage session",
            "complete three-provider session",
            "missing required field hard stop",
        ],
        "contract_change_policy": "Any contract revision after development performance is viewed requires a new untouched prospective population. The 65-session holdout cannot be evaluated under a revised contract.",
        "holdout_protection": {
            "holdout_values_must_not_be_loaded_during_development_validation": True,
            "holdout_partition_open_count": 1,
            "required_preconditions": ["contract tag verified", "development validation passed", "scoring implementation hash frozen"],
        },
        "evaluation_performed_by_this_plan": False,
    })


def freeze(output_dir: Path) -> dict[str, Any]:
    binding = verify_frozen_state()
    split, pair_counts = build_split()
    contract = build_contract(binding)
    audit = build_value_blindness_audit(binding)
    plan = build_validation_plan()
    artifacts = {
        "evaluation_contract.json": contract,
        "historical_split_manifest.json": split,
        "value_blindness_audit.json": audit,
        "implementation_validation_plan.json": plan,
    }
    for filename, artifact in artifacts.items():
        write_json(output_dir / filename, artifact)
    binding_manifest = with_fingerprint({
        "artifact_id": BINDING_ID,
        "artifact_type": "PACK_AE_CONTRACT_ARTIFACT_BINDING",
        "frozen_at": FROZEN_AT,
        "source_commit_before_contract_freeze": SOURCE_COMMIT,
        "artifact_fingerprints": {
            filename: artifact["artifact_fingerprint"] for filename, artifact in sorted(artifacts.items())
        },
        "artifact_file_sha256": {
            filename: sha256_file(output_dir / filename) for filename in sorted(artifacts)
        },
        "evaluation_performed": False,
        "provider_calls": 0,
        "apps_script_calls": 0,
        "spreadsheet_writes": 0,
    })
    write_json(output_dir / "binding_manifest.json", binding_manifest)
    return {
        "contract_id": CONTRACT_ID,
        "contract_fingerprint": contract["artifact_fingerprint"],
        "split_id": SPLIT_ID,
        "split_fingerprint": split["artifact_fingerprint"],
        "value_blindness_audit_fingerprint": audit["artifact_fingerprint"],
        "implementation_validation_plan_fingerprint": plan["artifact_fingerprint"],
        "binding_fingerprint": binding_manifest["artifact_fingerprint"],
        "development_pair_counts": pair_counts["HISTORICAL_DEVELOPMENT"],
        "holdout_pair_counts": pair_counts["HISTORICAL_CONFIRMATORY_HOLDOUT"],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    print(json.dumps(freeze(args.output_dir), sort_keys=True))


if __name__ == "__main__":
    main()
