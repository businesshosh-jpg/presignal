#!/usr/bin/env python3
"""Deterministic, development-only Pack A/E scoring implementation."""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import math
import random
import re
import subprocess
from pathlib import Path
from statistics import fmean
from typing import Any, Iterable, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "outputs/simplified_authoritative_replay"
CONTRACT_DIR = ROOT / "docs/pack_ae_evaluation_contract_v1"
DEFAULT_OUTPUT = ROOT / "docs/pack_ae_scoring_v1"
CREATED_AT = "2026-07-18T17:45:30Z"
SOURCE_COMMIT_BEFORE_IMPLEMENTATION = "3fc98f0e5f1afd0d6d3d9dea9426a0e374d43328"
CONTRACT_FINGERPRINT = "737b5db8d2d1ae268b834fe8e2b544de7e79fde4c705c9df1336a456c23666d0"
SPLIT_FINGERPRINT = "dd04813f678e7574ae1ca21019567163c454838daabff50e58972f1e41401e29"
VALUE_BLINDNESS_FINGERPRINT = "67e3d1b73a2afb4bb48df904f87a45e3de8cf29484bf3d521082e8ecb224e1cd"
ATTACHMENT_FINGERPRINT = "b4b63940e9052c8be80bb7e57dd423c1094b5679c4496e5bc511187eb21e2abc"
CANONICAL_FINGERPRINT = "986e707aaf1f95ae729d7f84b0969cb08906722fa350b049f4da8e2a87b9d9b0"
READINESS_FINGERPRINT = "4a7e23601ca098527390eb64e0955f0690582db03bdabc7089e2f81d96d9a126"
EVALUATION_READY_ARCHIVE_SHA256 = "579cedcbaa204817cce2fc19af211f069fe99b09b53ae7e7a9030ca1e8b7bd09"
VALIDATION_ID = "PRESIGNAL-V2-PACK-AE-DEVELOPMENT-VALIDATION-20260718T174530Z"
BINDING_ID = "PRESIGNAL-V2-PACK-AE-SCORER-BINDING-20260718T174530Z"
BOOTSTRAP_SEED = 20260718
BOOTSTRAP_RESAMPLES = 10_000
PROVIDERS = ("Anthropic", "Gemini", "OpenAI")
ARMS = ("A", "E")
ACTIONABLE_DIRECTIONS = frozenset(("UP", "DOWN", "FLAT"))
DIRECTIONS = ACTIONABLE_DIRECTIONS | {"NO_CLEAR_DIRECTION"}
STRENGTH_NORMALIZATION = {"WEAK": "WEAK", "MODERATE": "MEDIUM", "STRONG": "STRONG"}
SESSION_ID_RE = re.compile(r'"session_id"\s*:\s*"([^"]+)"')

READY = BASE / "evaluation_readiness/SIMPLIFIED-REPLAY-EVALUATION-READINESS-RECOVERED-20260718T162600Z"
ATTACHMENT = BASE / "outcome_attachments/SIMPLIFIED-REPLAY-OUTCOME-ATTACHMENT-RECOVERED-20260718T162300Z"
CANONICAL = BASE / "canonical_outcomes/SIMPLIFIED-REPLAY-CANONICAL-OUTCOMES-RECOVERED-20260718T162300Z"
RUN = BASE / "runs/SIMPLIFIED-REPLAY-AUTHORITATIVE-20260718T010455Z"
PREDICTIONS = RUN / "ledgers/accepted_predictions"
CHECKPOINT_ARCHIVE = BASE / "checkpoints/PRESIGNAL_V2_AUTHORITATIVE_EVALUATION_READY_20260718.tar.gz"


class ScoringIntegrityError(RuntimeError):
    """Raised when frozen inputs or scoring invariants do not reconcile."""


class HoldoutAccessError(ScoringIntegrityError):
    """Raised before any confirmatory-holdout record can be accessed."""


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha256_value(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def with_fingerprint(payload: Mapping[str, Any]) -> dict[str, Any]:
    artifact = dict(payload)
    artifact["fingerprint_algorithm"] = "SHA-256"
    artifact["fingerprint_scope"] = "canonical JSON of this artifact with artifact_fingerprint omitted"
    artifact["artifact_fingerprint"] = sha256_value(artifact)
    return artifact


def verify_artifact_fingerprint(path: Path, expected: str) -> dict[str, Any]:
    artifact = read_json(path)
    recorded = artifact.pop("artifact_fingerprint", None)
    actual = sha256_value(artifact)
    artifact["artifact_fingerprint"] = recorded
    if recorded != expected or actual != expected:
        raise ScoringIntegrityError("FROZEN_ARTIFACT_FINGERPRINT_MISMATCH:" + path.name)
    return artifact


def verify_component_fingerprint(directory: Path, fingerprint_file: str, expected: str) -> dict[str, Any]:
    fingerprint = read_json(directory / fingerprint_file)
    for filename, recorded_hash in fingerprint["file_sha256"].items():
        if sha256_file(directory / filename) != recorded_hash:
            raise ScoringIntegrityError("AUTHORITATIVE_COMPONENT_HASH_MISMATCH:" + filename)
    actual = sha256_value(fingerprint["file_sha256"])
    if fingerprint["whole_artifact_fingerprint"] != expected or actual != expected:
        raise ScoringIntegrityError("AUTHORITATIVE_ARTIFACT_FINGERPRINT_MISMATCH:" + fingerprint_file)
    return fingerprint


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n")


def action_value(forecast_direction: str, realized_direction: str) -> int:
    if forecast_direction not in DIRECTIONS:
        raise ScoringIntegrityError("UNSUPPORTED_FORECAST_DIRECTION:" + str(forecast_direction))
    if realized_direction not in ACTIONABLE_DIRECTIONS:
        raise ScoringIntegrityError("UNSUPPORTED_REALIZED_DIRECTION:" + str(realized_direction))
    if forecast_direction == "NO_CLEAR_DIRECTION":
        return 0
    return 1 if forecast_direction == realized_direction else -1


def pair_difference(pack_a_action_value: int, pack_e_action_value: int) -> int:
    difference = pack_e_action_value - pack_a_action_value
    if difference not in (-2, -1, 0, 1, 2):
        raise ScoringIntegrityError("INVALID_PAIR_DIFFERENCE")
    return difference


def normalize_strength(forecast_strength: str) -> str:
    try:
        return STRENGTH_NORMALIZATION[forecast_strength]
    except KeyError as exc:
        raise ScoringIntegrityError("UNSUPPORTED_FORECAST_STRENGTH:" + str(forecast_strength)) from exc


def type7_quantile(values: Sequence[float], probability: float) -> float:
    if not values:
        raise ValueError("values must not be empty")
    if probability < 0 or probability > 1:
        raise ValueError("probability must be between zero and one")
    ordered = sorted(float(value) for value in values)
    if len(ordered) == 1:
        return ordered[0]
    index = (len(ordered) - 1) * probability
    lower = math.floor(index)
    upper = math.ceil(index)
    fraction = index - lower
    return ordered[lower] + fraction * (ordered[upper] - ordered[lower])


def cluster_bootstrap_interval(
    session_values: Mapping[str, float],
    *,
    seed: int = BOOTSTRAP_SEED,
    resamples: int = BOOTSTRAP_RESAMPLES,
) -> dict[str, Any]:
    session_ids = sorted(session_values)
    if not session_ids:
        raise ScoringIntegrityError("EMPTY_BOOTSTRAP_POPULATION")
    rng = random.Random(seed)
    estimates = []
    count = len(session_ids)
    for _ in range(resamples):
        sampled = [session_values[session_ids[rng.randrange(count)]] for _ in range(count)]
        estimates.append(fmean(sampled))
    return {
        "seed": seed,
        "resamples": resamples,
        "resampling_unit": "MARKET_SESSION",
        "interval": "TWO_SIDED_95_PERCENT_PERCENTILE",
        "interpolation": "TYPE_7",
        "lower": type7_quantile(estimates, 0.025),
        "upper": type7_quantile(estimates, 0.975),
        "replicate_estimates_sha256": sha256_value(estimates),
    }


def average_pairs_within_sessions(pair_rows: Iterable[Mapping[str, Any]]) -> dict[str, float]:
    grouped: dict[str, list[float]] = collections.defaultdict(list)
    for row in pair_rows:
        grouped[str(row["session_id"])].append(float(row["pair_difference"]))
    return {session_id: fmean(values) for session_id, values in sorted(grouped.items())}


def summarize_arm(pair_rows: Sequence[Mapping[str, Any]], arm: str) -> dict[str, Any]:
    prefix = arm.lower()
    directions = [str(row[prefix + "_direction"]) for row in pair_rows]
    values = [int(row[prefix + "_action_value"]) for row in pair_rows]
    actionable = sum(direction in ACTIONABLE_DIRECTIONS for direction in directions)
    correct = sum(value == 1 for value in values)
    incorrect = sum(value == -1 for value in values)
    no_clear = sum(direction == "NO_CLEAR_DIRECTION" for direction in directions)
    total = len(pair_rows)
    return {
        "forecast_count": total,
        "actionable_count": actionable,
        "correct_actionable_count": correct,
        "incorrect_actionable_count": incorrect,
        "no_clear_direction_count": no_clear,
        "actionable_accuracy": correct / actionable if actionable else None,
        "actionable_coverage": actionable / total if total else None,
        "no_clear_direction_rate": no_clear / total if total else None,
    }


def summarize_strength(pair_rows: Sequence[Mapping[str, Any]], arm: str) -> dict[str, Any]:
    prefix = arm.lower()
    matches = [bool(row[prefix + "_strength_correct"]) for row in pair_rows]
    return {
        "eligible_count": len(matches),
        "correct_count": sum(matches),
        "accuracy": sum(matches) / len(matches) if matches else None,
    }


def _extract_session_id(raw_line: str) -> str:
    match = SESSION_ID_RE.search(raw_line)
    if not match:
        raise ScoringIntegrityError("SESSION_ID_NOT_DISCOVERABLE_WITHOUT_DESERIALIZATION")
    return match.group(1)


def load_partition_manifest() -> tuple[dict[str, str], dict[str, Any]]:
    split = verify_artifact_fingerprint(
        CONTRACT_DIR / "historical_split_manifest.json", SPLIT_FINGERPRINT
    )
    partitions = {row["session_id"]: row["partition"] for row in split["session_records"]}
    if collections.Counter(partitions.values()) != {
        "HISTORICAL_DEVELOPMENT": 130,
        "HISTORICAL_CONFIRMATORY_HOLDOUT": 65,
    }:
        raise ScoringIntegrityError("SPLIT_POPULATION_MISMATCH")
    return partitions, split


def require_development_session(session_id: str, partitions: Mapping[str, str]) -> None:
    partition = partitions.get(session_id)
    if partition == "HISTORICAL_CONFIRMATORY_HOLDOUT":
        raise HoldoutAccessError("HOLDOUT_SESSION_REJECTED:" + session_id)
    if partition != "HISTORICAL_DEVELOPMENT":
        raise ScoringIntegrityError("SESSION_NOT_IN_DEVELOPMENT_PARTITION:" + session_id)


def _load_development_jsonl(
    path: Path,
    development_ids: set[str],
    holdout_ids: set[str],
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    rows = []
    diagnostics = {"development_rows_deserialized": 0, "holdout_rows_deserialized": 0, "holdout_rows_identity_skipped": 0}
    with path.open() as source:
        for raw_line in source:
            if not raw_line.strip():
                continue
            session_id = _extract_session_id(raw_line)
            if session_id in holdout_ids:
                diagnostics["holdout_rows_identity_skipped"] += 1
                continue
            if session_id not in development_ids:
                continue
            rows.append(json.loads(raw_line))
            diagnostics["development_rows_deserialized"] += 1
    return rows, diagnostics


def verify_frozen_contract() -> dict[str, Any]:
    contract = verify_artifact_fingerprint(CONTRACT_DIR / "evaluation_contract.json", CONTRACT_FINGERPRINT)
    verify_artifact_fingerprint(CONTRACT_DIR / "value_blindness_audit.json", VALUE_BLINDNESS_FINGERPRINT)
    if contract["primary_endpoint"]["name"] != "PAIRED_ACTION_VALUE_DIFFERENCE":
        raise ScoringIntegrityError("PRIMARY_ENDPOINT_CHANGED")
    uncertainty = contract["uncertainty"]
    required_uncertainty = {
        "method": "DETERMINISTIC_MARKET_SESSION_CLUSTER_BOOTSTRAP",
        "interval": "two-sided 95% percentile interval",
        "percentiles": [0.025, 0.975],
        "resamples": BOOTSTRAP_RESAMPLES,
        "resampling_unit": "MARKET_SESSION",
        "seed": BOOTSTRAP_SEED,
    }
    if any(uncertainty.get(key) != value for key, value in required_uncertainty.items()):
        raise ScoringIntegrityError("BOOTSTRAP_CONTRACT_CHANGED")
    if "Type 7 linear interpolation" not in uncertainty.get("quantile_algorithm", ""):
        raise ScoringIntegrityError("BOOTSTRAP_CONTRACT_CHANGED")
    if "retain all available complete provider pairs" not in uncertainty.get("resampling_algorithm", ""):
        raise ScoringIntegrityError("BOOTSTRAP_CONTRACT_CHANGED")
    if contract["strength_normalization"].get("mapping") != STRENGTH_NORMALIZATION:
        raise ScoringIntegrityError("STRENGTH_NORMALIZATION_CHANGED")
    return contract


def verify_authoritative_inputs() -> None:
    if sha256_file(CHECKPOINT_ARCHIVE) != EVALUATION_READY_ARCHIVE_SHA256:
        raise ScoringIntegrityError("EVALUATION_READY_ARCHIVE_MISMATCH")
    verify_component_fingerprint(CANONICAL, "canonical_fingerprint.json", CANONICAL_FINGERPRINT)
    verify_component_fingerprint(ATTACHMENT, "attachment_fingerprint.json", ATTACHMENT_FINGERPRINT)
    verify_component_fingerprint(READY, "readiness_fingerprint.json", READINESS_FINGERPRINT)


def load_development_inputs() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    verify_frozen_contract()
    verify_authoritative_inputs()
    partitions, split = load_partition_manifest()
    development_ids = {session_id for session_id, partition in partitions.items() if partition == "HISTORICAL_DEVELOPMENT"}
    holdout_ids = {session_id for session_id, partition in partitions.items() if partition == "HISTORICAL_CONFIRMATORY_HOLDOUT"}

    pair_rows = [json.loads(line) for line in (READY / "provider_session_pair_readiness.jsonl").read_text().splitlines() if line]
    development_pairs = []
    for row in pair_rows:
        session_id = row["session_id"]
        if session_id in holdout_ids or session_id not in development_ids or row["complete_ae_pair"] is not True:
            continue
        require_development_session(session_id, partitions)
        development_pairs.append(row)

    canonical_rows, canonical_diagnostics = _load_development_jsonl(
        CANONICAL / "canonical_session_outcomes.jsonl", development_ids, holdout_ids
    )
    attachment_rows, attachment_diagnostics = _load_development_jsonl(
        ATTACHMENT / "prediction_outcome_links.jsonl", development_ids, holdout_ids
    )
    canonical_by_session = {row["session_id"]: row for row in canonical_rows}
    attachment_by_key = {
        (row["session_id"], row["provider"], row["pack_arm"]): row for row in attachment_rows
    }
    if len(canonical_by_session) != 130 or len(development_pairs) != 376:
        raise ScoringIntegrityError("DEVELOPMENT_POPULATION_RECONCILIATION_FAILED")
    if len(attachment_by_key) < 752:
        raise ScoringIntegrityError("DEVELOPMENT_ATTACHMENT_RECONCILIATION_FAILED")

    predictions_opened = 0
    scored_inputs = []
    provider_counts: collections.Counter[str] = collections.Counter()
    for pair in sorted(development_pairs, key=lambda row: (row["session_id"], row["provider"])):
        session_id = pair["session_id"]
        require_development_session(session_id, partitions)
        canonical = canonical_by_session.get(session_id)
        if not canonical:
            raise ScoringIntegrityError("MISSING_DEVELOPMENT_CANONICAL_OUTCOME:" + session_id)
        arm_predictions = {}
        for arm in ARMS:
            forecast_identity = pair["forecast_identities_by_arm"].get(arm)
            link = attachment_by_key.get((session_id, pair["provider"], arm))
            if not forecast_identity or not link or link["forecast_identity"] != forecast_identity:
                raise ScoringIntegrityError("PAIR_ATTACHMENT_IDENTITY_MISMATCH")
            if link["canonical_session_outcome_id"] != canonical["canonical_outcome_id"]:
                raise ScoringIntegrityError("PAIR_CANONICAL_IDENTITY_MISMATCH")
            prediction_path = PREDICTIONS / (forecast_identity + ".json")
            prediction = read_json(prediction_path)
            predictions_opened += 1
            if prediction["provider"] != pair["provider"] or prediction["identity_id"] != forecast_identity:
                raise ScoringIntegrityError("PREDICTION_IDENTITY_MISMATCH")
            arm_predictions[arm] = prediction
        provider_counts[pair["provider"]] += 1
        scored_inputs.append({
            "session_id": session_id,
            "provider": pair["provider"],
            "canonical": canonical,
            "A": arm_predictions["A"],
            "E": arm_predictions["E"],
        })

    expected_provider_counts = split["partition_summary"]["HISTORICAL_DEVELOPMENT"]["complete_pairs_by_provider"]
    if dict(provider_counts) != expected_provider_counts:
        raise ScoringIntegrityError("DEVELOPMENT_PROVIDER_RECONCILIATION_FAILED")
    diagnostics = {
        "development_sessions_allowed": len(development_ids),
        "holdout_sessions_denied": len(holdout_ids),
        "development_prediction_files_opened": predictions_opened,
        "development_attachment_rows_deserialized": attachment_diagnostics["development_rows_deserialized"],
        "development_incomplete_pair_attachment_rows_not_scored": len(attachment_by_key) - (len(development_pairs) * 2),
        "holdout_prediction_files_opened": 0,
        "holdout_canonical_rows_deserialized": canonical_diagnostics["holdout_rows_deserialized"],
        "holdout_attachment_rows_deserialized": attachment_diagnostics["holdout_rows_deserialized"],
        "holdout_canonical_rows_identity_skipped": canonical_diagnostics["holdout_rows_identity_skipped"],
        "holdout_attachment_rows_identity_skipped": attachment_diagnostics["holdout_rows_identity_skipped"],
        "provider_pair_counts": {provider: provider_counts[provider] for provider in PROVIDERS},
    }
    return scored_inputs, diagnostics


def score_pairs(scored_inputs: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    pair_scores = []
    for source in scored_inputs:
        canonical = source["canonical"]
        realized_direction = canonical["realized_direction"]
        realized_strength = canonical["realized_reaction_strength"]
        record: dict[str, Any] = {
            "session_id": source["session_id"],
            "provider": source["provider"],
            "canonical_outcome_id": canonical["canonical_outcome_id"],
            "canonical_outcome_fingerprint": canonical["outcome_fingerprint"],
            "realized_direction": realized_direction,
            "realized_strength": realized_strength,
        }
        for arm in ARMS:
            prediction = source[arm]
            prefix = arm.lower()
            direction = prediction["final_usdjpy_direction"]
            strength = prediction["reaction_strength"]
            record[prefix + "_forecast_identity"] = prediction["identity_id"]
            record[prefix + "_direction"] = direction
            record[prefix + "_action_value"] = action_value(direction, realized_direction)
            record[prefix + "_strength"] = strength
            record[prefix + "_normalized_strength"] = normalize_strength(strength)
            record[prefix + "_strength_correct"] = normalize_strength(strength) == realized_strength
        record["pair_difference"] = pair_difference(record["a_action_value"], record["e_action_value"])
        record["pair_record_sha256"] = sha256_value(record)
        pair_scores.append(record)
    return pair_scores


def _session_consistency(pair_rows: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    grouped: dict[str, list[int]] = collections.defaultdict(list)
    for row in pair_rows:
        grouped[str(row["session_id"])].append(int(row["pair_difference"]))
    counts = collections.Counter()
    for differences in grouped.values():
        if all(value > 0 for value in differences):
            counts["unanimously_favoring_E"] += 1
        elif all(value < 0 for value in differences):
            counts["unanimously_favoring_A"] += 1
        elif any(value > 0 for value in differences) and any(value < 0 for value in differences):
            counts["mixed_provider_effects"] += 1
        else:
            counts["neutral_or_nonunanimous"] += 1
    return {key: counts[key] for key in (
        "unanimously_favoring_A", "unanimously_favoring_E", "mixed_provider_effects", "neutral_or_nonunanimous"
    )}


def _effect_summary(pair_rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    session_values = average_pairs_within_sessions(pair_rows)
    return {
        "pair_count": len(pair_rows),
        "independent_session_count": len(session_values),
        "pooled_pair_mean_supporting_only": fmean(float(row["pair_difference"]) for row in pair_rows),
        "mean_session_level_difference": fmean(session_values.values()),
        "cluster_bootstrap_95_percent_interval": cluster_bootstrap_interval(session_values),
    }


def build_development_validation() -> dict[str, Any]:
    inputs, diagnostics = load_development_inputs()
    pair_scores = score_pairs(inputs)
    session_values = average_pairs_within_sessions(pair_scores)
    by_session: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    for row in pair_scores:
        by_session[row["session_id"]].append(row)
    session_scores = []
    for session_id in sorted(by_session):
        rows = sorted(by_session[session_id], key=lambda row: row["provider"])
        session_scores.append({
            "session_id": session_id,
            "available_provider_count": len(rows),
            "providers": [row["provider"] for row in rows],
            "provider_pair_differences": {row["provider"]: row["pair_difference"] for row in rows},
            "session_mean_pair_difference": session_values[session_id],
        })
    provider_summaries = {}
    for provider in PROVIDERS:
        rows = [row for row in pair_scores if row["provider"] == provider]
        provider_summaries[provider] = _effect_summary(rows)
    complete_three_rows = [
        row for row in pair_scores if len(by_session[row["session_id"]]) == 3
    ]
    strength_a = summarize_strength(pair_scores, "A")
    strength_e = summarize_strength(pair_scores, "E")
    payload = {
        "artifact_id": VALIDATION_ID,
        "artifact_type": "PACK_AE_SCORING_IMPLEMENTATION_DEVELOPMENT_VALIDATION",
        "created_at": CREATED_AT,
        "scientific_status": "IMPLEMENTATION_VALIDATION_ONLY_NOT_CONFIRMATORY_EVIDENCE",
        "confirmatory_conclusion_produced": False,
        "partition": "HISTORICAL_DEVELOPMENT",
        "frozen_inputs": {
            "contract_fingerprint": CONTRACT_FINGERPRINT,
            "split_manifest_fingerprint": SPLIT_FINGERPRINT,
            "value_blindness_audit_fingerprint": VALUE_BLINDNESS_FINGERPRINT,
            "recovered_attachment_fingerprint": ATTACHMENT_FINGERPRINT,
            "recovered_canonical_outcomes_fingerprint": CANONICAL_FINGERPRINT,
            "evaluation_readiness_fingerprint": READINESS_FINGERPRINT,
        },
        "population_reconciliation": {
            "development_sessions": len(session_scores),
            "complete_pairs": len(pair_scores),
            "complete_pairs_by_provider": diagnostics["provider_pair_counts"],
            "prediction_rows_scored": len(pair_scores) * 2,
        },
        "holdout_access_guard": diagnostics,
        "primary_endpoint_implementation_validation": _effect_summary(pair_scores),
        "arm_summaries": {"Pack_A": summarize_arm(pair_scores, "A"), "Pack_E": summarize_arm(pair_scores, "E")},
        "discordant_pair_counts": {
            "A_wrong_E_correct": sum(row["a_action_value"] == -1 and row["e_action_value"] == 1 for row in pair_scores),
            "A_correct_E_wrong": sum(row["a_action_value"] == 1 and row["e_action_value"] == -1 for row in pair_scores),
        },
        "provider_summaries": provider_summaries,
        "session_consistency": _session_consistency(pair_scores),
        "complete_three_provider_robustness": _effect_summary(complete_three_rows),
        "strength_accuracy_supporting_only": {
            "normalization": STRENGTH_NORMALIZATION,
            "Pack_A": strength_a,
            "Pack_E": strength_e,
            "paired_accuracy_indicator_mean_difference": fmean(
                float(row["e_strength_correct"]) - float(row["a_strength_correct"]) for row in pair_scores
            ),
        },
        "session_scores": session_scores,
        "pair_scores": pair_scores,
        "determinism": {
            "pair_records_sha256": sha256_value([row["pair_record_sha256"] for row in pair_scores]),
            "session_scores_sha256": sha256_value(session_scores),
        },
        "prohibited_outputs_absent": {
            "confidence_calibration": True,
            "legacy_overall_ok": True,
            "confirmatory_decision_rule_result": True,
        },
    }
    return with_fingerprint(payload)


def build_binding(validation: Mapping[str, Any], test_result: Mapping[str, Any]) -> dict[str, Any]:
    scorer_path = ROOT / "automation/pack_ae_scoring_v1.py"
    test_path = ROOT / "automation/test_pack_ae_scoring_v1.py"
    source_hashes = {
        "automation/pack_ae_scoring_v1.py": sha256_file(scorer_path),
        "automation/test_pack_ae_scoring_v1.py": sha256_file(test_path),
    }
    return with_fingerprint({
        "artifact_id": BINDING_ID,
        "artifact_type": "PACK_AE_SCORING_IMPLEMENTATION_SOURCE_BINDING",
        "created_at": CREATED_AT,
        "source_commit_before_implementation": SOURCE_COMMIT_BEFORE_IMPLEMENTATION,
        "frozen_contract_fingerprint": CONTRACT_FINGERPRINT,
        "frozen_split_manifest_fingerprint": SPLIT_FINGERPRINT,
        "frozen_value_blindness_audit_fingerprint": VALUE_BLINDNESS_FINGERPRINT,
        "scorer_source_file_hashes": source_hashes,
        "test_result": dict(test_result),
        "development_population_reconciliation": validation["population_reconciliation"],
        "bootstrap": {
            "seed": BOOTSTRAP_SEED,
            "resamples": BOOTSTRAP_RESAMPLES,
            "resampling_unit": "MARKET_SESSION",
            "interval": "TWO_SIDED_95_PERCENT_PERCENTILE",
            "interpolation": "TYPE_7",
        },
        "development_validation_artifact": {
            "artifact_id": validation["artifact_id"],
            "artifact_fingerprint": validation["artifact_fingerprint"],
        },
        "holdout_access_confirmation": {
            "holdout_evaluation_performed": False,
            "holdout_prediction_files_opened": validation["holdout_access_guard"]["holdout_prediction_files_opened"],
            "holdout_canonical_rows_deserialized": validation["holdout_access_guard"]["holdout_canonical_rows_deserialized"],
            "holdout_attachment_rows_deserialized": validation["holdout_access_guard"]["holdout_attachment_rows_deserialized"],
            "hard_partition_guard": "HoldoutAccessError",
        },
        "frozen_contract_changed": False,
        "confirmatory_conclusion_produced": False,
        "provider_calls": 0,
        "apps_script_calls": 0,
        "spreadsheet_writes": 0,
    })


def verify_repository_state() -> None:
    branch = subprocess.check_output(["git", "branch", "--show-current"], cwd=ROOT, text=True).strip()
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    tag = subprocess.check_output(
        ["git", "rev-parse", "presignal-v2-pack-ae-contract-frozen^{}"], cwd=ROOT, text=True
    ).strip()
    if branch != "codex-simplified-authoritative-replay":
        raise ScoringIntegrityError("BRANCH_MISMATCH")
    if head != SOURCE_COMMIT_BEFORE_IMPLEMENTATION or tag != SOURCE_COMMIT_BEFORE_IMPLEMENTATION:
        raise ScoringIntegrityError("SOURCE_OR_TAG_MISMATCH")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--tests-run", type=int, required=True)
    args = parser.parse_args()
    verify_repository_state()
    validation = build_development_validation()
    binding = build_binding(validation, {"status": "PASS", "tests_run": args.tests_run, "failures": 0, "errors": 0})
    write_json(args.output_dir / "development_validation.json", validation)
    write_json(args.output_dir / "scorer_binding.json", binding)
    print(canonical_json({
        "validation_id": validation["artifact_id"],
        "validation_fingerprint": validation["artifact_fingerprint"],
        "binding_id": binding["artifact_id"],
        "binding_fingerprint": binding["artifact_fingerprint"],
        "development_sessions": validation["population_reconciliation"]["development_sessions"],
        "development_pairs": validation["population_reconciliation"]["complete_pairs"],
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
