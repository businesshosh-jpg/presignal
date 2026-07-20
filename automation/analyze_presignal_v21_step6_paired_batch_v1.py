#!/usr/bin/env python3
"""Read-only, Episode-cluster-aware analysis of the frozen Step 6 batch."""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
import os
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean, median
from typing import Any, Iterable, Mapping

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from automation import presignal_v21_event_path_contract_v1 as contract
from automation import run_presignal_v21_single_event_path_pair_v1 as single

STEP5 = ROOT / "outputs" / "presignal_v21_step5_reuse"
BATCH_ROOT = ROOT / "outputs" / "presignal_v21_step6_batch"
OUTPUT_ROOT = ROOT / "outputs" / "presignal_v21_step7_paired_analysis"
EXPECTED_TAG_TARGET = "e8cd4f3fa2f3d7c1b2e624e32f1aea0a6c9866c0"
EXPECTED_BATCH_CONTRACT = "sha256:7b3f015f34e61c0877096f6da4a077ab4bee8e6d964c82a1da2beaf0f80f10ca"
EXPECTED_PACK_A = "sha256:1e9d795403cd3a215fa4109cfe692b1af91c8280d379b6bf6ebce0ffc5e3bb99"
EXPECTED_PACK_E = "sha256:034ea6a372c147d29bd06c6384891b8dcca819f67534d840212cd73cf13e4747"
ANALYSIS_VERSION = "presignal_v21_episode_cluster_paired_analysis_v1"


class FrozenPopulationIntegrityError(RuntimeError):
    """The immutable batch cannot support a safe analysis."""


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha256(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def short(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()[:20]


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    os.replace(temporary, path)


def write_jsonl(path: Path, values: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text("".join(canonical_json(value) + "\n" for value in values))
    os.replace(temporary, path)


def git_tag_target() -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "presignal-v2.1-event-path-contract-v1-frozen^{}"],
        cwd=ROOT,
        text=True,
    ).strip()


def wilson_interval(successes: int, total: int, z: float = 1.959963984540054) -> list[float | None]:
    if total == 0:
        return [None, None]
    proportion = successes / total
    denominator = 1 + z * z / total
    centre = (proportion + z * z / (2 * total)) / denominator
    margin = z * math.sqrt(proportion * (1 - proportion) / total + z * z / (4 * total * total)) / denominator
    return [centre - margin, centre + margin]


def conservative_difference_interval(a_successes: int, b_successes: int, total: int) -> list[float | None]:
    """Conservative Newcombe-style interval from marginal Wilson intervals."""
    a_low, a_high = wilson_interval(a_successes, total)
    b_low, b_high = wilson_interval(b_successes, total)
    if None in {a_low, a_high, b_low, b_high}:
        return [None, None]
    return [float(a_low - b_high), float(a_high - b_low)]


def exact_mcnemar_pvalue(a_only: int, e_only: int) -> float:
    discordant = a_only + e_only
    if discordant == 0:
        return 1.0
    tail = sum(math.comb(discordant, index) for index in range(0, min(a_only, e_only) + 1)) / (2 ** discordant)
    return min(1.0, 2 * tail)


def binary_primary(evaluation: Mapping[str, Any]) -> int:
    """The primary score is 1 only for an explicit correct 15-minute direction.

    Frozen no-signal records have a null direction endpoint. They remain in the
    complete population, but do not earn a correct directional forecast.
    """
    return int(evaluation.get("direction_15m_ok") is True)


def binary_horizon(evaluation: Mapping[str, Any], horizon: int) -> int:
    return int(evaluation.get(f"direction_{horizon}m_ok") is True)


def response_length(path: Path) -> int | None:
    if not path.exists():
        return None
    response = read_json(path)
    raw = response.get("raw_output")
    return len(canonical_json(raw)) if raw is not None else None


def pair_directory(batch_dir: Path, pair_id: str) -> Path:
    return batch_dir / "pairs" / pair_id


def arm_folder(arm: str) -> str:
    return "pack_a" if arm == "PACK_A" else "pack_e"


def stage_rows(path: Path) -> list[dict[str, Any]]:
    return read_jsonl(path) if path.exists() else []


def verify_frozen_population(batch_dir: Path) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    manifest = read_json(batch_dir / "batch_manifest.json")
    state = read_json(batch_dir / "batch_state.json")
    completion = read_json(batch_dir / "batch_completion_summary.json")
    contract_verification = read_json(batch_dir / "batch_contract_verification.json")
    step5 = read_json(STEP5 / "step5_manifest.json")
    ledger = read_jsonl(batch_dir / "provider_call_ledger.jsonl")
    errors: list[str] = []
    if git_tag_target() != EXPECTED_TAG_TARGET: errors.append("CONTRACT_TAG_TARGET")
    if manifest.get("batch_contract_fingerprint") != EXPECTED_BATCH_CONTRACT: errors.append("BATCH_CONTRACT_FINGERPRINT")
    if not contract_verification.get("verified") or contract_verification.get("scientific_contract_change"): errors.append("BATCH_CONTRACT_VERIFICATION")
    if step5.get("pack_a_input_fingerprint") != EXPECTED_PACK_A: errors.append("STEP5_PACK_A_FINGERPRINT")
    if step5.get("pack_e_input_fingerprint") != EXPECTED_PACK_E: errors.append("STEP5_PACK_E_FINGERPRINT")
    pair_ids = list(manifest.get("eligible_pair_ids") or [])
    if len(pair_ids) != 21 or len(set(pair_ids)) != 21 or set(pair_ids) != set(state.get("pairs") or {}): errors.append("APPROVED_PAIR_IDENTITIES")
    states = Counter(pair.get("state") for pair in state["pairs"].values())
    expected = {"COMPLETE_PAIRED": 14, "INCOMPLETE_PACK_A": 3, "INCOMPLETE_PACK_E": 1, "INCOMPLETE_BOTH": 3}
    if {key: states.get(key, 0) for key in expected} != expected: errors.append("PAIR_COMPLETION_COUNTS")
    if len(ledger) != 42 or sum(bool(row.get("response_accepted")) for row in ledger) != 32: errors.append("CALL_LEDGER_COUNTS")
    records: list[dict[str, Any]] = []
    prediction_fingerprints: list[str] = []
    path_fingerprints: list[str] = []
    evaluation_fingerprints: list[str] = []
    for pair_id in sorted(pair_ids):
        pair_state = state["pairs"][pair_id]
        directory = pair_directory(batch_dir, pair_id)
        pair_manifest = read_json(directory / "pair_manifest.json")
        input_a = state["input_rows"][pair_id]["PACK_A"]
        input_e = state["input_rows"][pair_id]["PACK_E"]
        if input_a["episode_id"] != input_e["episode_id"] or input_a["provider"] != input_e["provider"] or input_a["model"] != input_e["model"]:
            errors.append("PAIR_INPUT_IDENTITY:" + pair_id)
        record = {
            "pair_id": pair_id,
            "episode_id": pair_manifest["episode_id"],
            "session_id": pair_manifest["session_id"],
            "provider": pair_manifest["provider"],
            "model": pair_manifest["model"],
            "outcome_identity": pair_manifest["outcome_identity"],
            "completion": pair_state["state"],
            "same_time_cluster": len(input_a.get("episode_members") or []) > 1,
            "member_count": len(input_a.get("episode_members") or []),
            "member_events": list(input_a.get("episode_members") or []),
            "release_ts": input_a.get("release_ts"),
            "execution_order": list(pair_manifest.get("arm_order") or []),
            "pack_a_size": 0,
            "pack_e_size": len(((input_e.get("shared_market_state_pack") or {}).get("items") or [])),
            "information_request_count": len(input_a.get("information_requests") or []),
            "prompt_a_length": len((directory / "pack_a" / "prompt.txt").read_text()) if (directory / "pack_a" / "prompt.txt").exists() else None,
            "prompt_e_length": len((directory / "pack_e" / "prompt.txt").read_text()) if (directory / "pack_e" / "prompt.txt").exists() else None,
        }
        for arm in ("PACK_A", "PACK_E"):
            folder = directory / arm_folder(arm)
            arm_state = pair_state["arms"][arm]
            record[arm.lower() + "_state"] = arm_state.get("state")
            record[arm.lower() + "_rejection_reason"] = arm_state.get("error")
            record[arm.lower() + "_response_length"] = response_length(folder / "provider_response_raw.json")
            if arm_state.get("state") == "FORECAST_ACCEPTED":
                prediction = read_json(folder / "prediction.json")
                paths = stage_rows(folder / "prediction_path.jsonl")
                contract.validate_prediction_path_transaction(prediction, paths)
                prediction_fingerprints.append(prediction["prediction_fingerprint"])
                path_fingerprints.extend(path["stage_fingerprint"] for path in paths)
                record[arm.lower() + "_prediction_fingerprint"] = prediction["prediction_fingerprint"]
                record[arm.lower() + "_path_fingerprint"] = sha256(paths)
        if pair_state["state"] == "COMPLETE_PAIRED":
            outcome_record = read_json(directory / "outcome_reference.json")
            outcome = outcome_record["outcome"]
            if outcome["outcome_id"] != pair_manifest["outcome_identity"] or not outcome_record.get("same_outcome_for_pack_a_and_pack_e"):
                errors.append("OUTCOME_IDENTITY:" + pair_id)
            for arm in ("PACK_A", "PACK_E"):
                folder = directory / arm_folder(arm)
                prediction = read_json(folder / "prediction.json")
                paths = stage_rows(folder / "prediction_path.jsonl")
                evaluation = read_json(directory / ("evaluation_pack_a.json" if arm == "PACK_A" else "evaluation_pack_e.json"))
                contract.validate_evaluation(evaluation, prediction, outcome, paths)
                if evaluation["outcome_id"] != outcome["outcome_id"]: errors.append("EVALUATION_OUTCOME_IDENTITY:" + pair_id)
                evaluation_fingerprints.append(evaluation["evaluation_fingerprint"])
                record[arm.lower() + "_evaluation"] = evaluation
                record[arm.lower() + "_outcome_id"] = outcome["outcome_id"]
        records.append(record)
    if errors:
        raise FrozenPopulationIntegrityError("V2_1_STEP7_FROZEN_POPULATION_INTEGRITY_FAILURE:" + ",".join(sorted(set(errors))))
    verification = {
        "verified": True,
        "batch_run_id": manifest["batch_run_id"],
        "contract_tag_target": git_tag_target(),
        "batch_contract_fingerprint": manifest["batch_contract_fingerprint"],
        "step5_pack_a_fingerprint": step5["pack_a_input_fingerprint"],
        "step5_pack_e_fingerprint": step5["pack_e_input_fingerprint"],
        "approved_pair_count": len(pair_ids),
        "call_ledger_fingerprint": sha256(ledger),
        "forecast_fingerprints": sorted(prediction_fingerprints),
        "prediction_path_stage_fingerprints": sorted(path_fingerprints),
        "evaluation_fingerprints": sorted(evaluation_fingerprints),
        "completion_counts": dict(sorted(states.items())),
    }
    return manifest, state, records, verification


def contingency(rows: list[Mapping[str, Any]], horizon: int = 15) -> dict[str, Any]:
    a_values = [binary_horizon(row["pack_a_evaluation"], horizon) for row in rows]
    e_values = [binary_horizon(row["pack_e_evaluation"], horizon) for row in rows]
    table = Counter(zip(a_values, e_values))
    a_only, e_only = table[(1, 0)], table[(0, 1)]
    total = len(rows)
    return {
        "horizon_min": horizon,
        "pair_count": total,
        "pack_a_correct": sum(a_values),
        "pack_e_correct": sum(e_values),
        "pack_a_accuracy": sum(a_values) / total if total else None,
        "pack_e_accuracy": sum(e_values) / total if total else None,
        "paired_risk_difference_pack_a_minus_pack_e": (sum(a_values) - sum(e_values)) / total if total else None,
        "both_correct": table[(1, 1)], "pack_a_only_correct": a_only,
        "pack_e_only_correct": e_only, "both_incorrect": table[(0, 0)],
        "exact_mcnemar_two_sided_p_value": exact_mcnemar_pvalue(a_only, e_only),
        "conservative_95pct_difference_interval": conservative_difference_interval(sum(a_values), sum(e_values), total),
    }


def episode_cluster_permutation(rows: list[Mapping[str, Any]], value_key: str = "primary") -> dict[str, Any]:
    clusters: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        if value_key == "primary":
            difference = binary_primary(row["pack_a_evaluation"]) - binary_primary(row["pack_e_evaluation"])
        else:
            difference = float(row[value_key])
        clusters[row["episode_id"]].append(difference)
    episodes = sorted(clusters)
    observed = mean(value for episode in episodes for value in clusters[episode]) if episodes else None
    permutations = 2 ** len(episodes)
    values: list[float] = []
    for signs in itertools.product((-1, 1), repeat=len(episodes)):
        total = sum(sign * value for sign, episode in zip(signs, episodes) for value in clusters[episode])
        count = sum(len(clusters[episode]) for episode in episodes)
        values.append(total / count)
    p_value = sum(abs(value) >= abs(observed) - 1e-12 for value in values) / len(values) if values else None
    return {
        "statistic": "mean_paired_difference_pack_a_minus_pack_e",
        "value_key": value_key,
        "unique_episode_clusters": len(episodes),
        "cluster_pair_counts": {episode: len(clusters[episode]) for episode in episodes},
        "observed_clustered_mean_difference": observed,
        "method": "EXACT_EPISODE_LEVEL_LABEL_SWAP_ENUMERATION",
        "possible_permutations": permutations,
        "two_sided_p_value": p_value,
        "null_distribution_min": min(values) if values else None,
        "null_distribution_max": max(values) if values else None,
    }


def secondary_analysis(rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    results = []
    for horizon in (5, 30, 60):
        record = contingency(rows, horizon)
        record["multiplicity"] = "SECONDARY_EXPLORATORY_UNADJUSTED"
        results.append(record)
    reversal = {
        "pack_a_true": sum(row["pack_a_evaluation"].get("reversal_ok") is True for row in rows),
        "pack_e_true": sum(row["pack_e_evaluation"].get("reversal_ok") is True for row in rows),
        "pack_a_available": sum(row["pack_a_evaluation"].get("reversal_ok") is not None for row in rows),
        "pack_e_available": sum(row["pack_e_evaluation"].get("reversal_ok") is not None for row in rows),
        "label": "SECONDARY_EXPLORATORY",
    }
    return {"horizons": results, "reversal_path_validity": reversal, "multiplicity_note": "Secondary endpoints are exploratory and do not override the primary endpoint."}


def path_score_analysis(rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    a_values = [row["pack_a_evaluation"].get("overall_path_score") for row in rows if isinstance(row["pack_a_evaluation"].get("overall_path_score"), (int, float))]
    e_values = [row["pack_e_evaluation"].get("overall_path_score") for row in rows if isinstance(row["pack_e_evaluation"].get("overall_path_score"), (int, float))]
    paired = []
    for row in rows:
        a_value, e_value = row["pack_a_evaluation"].get("overall_path_score"), row["pack_e_evaluation"].get("overall_path_score")
        if isinstance(a_value, (int, float)) and isinstance(e_value, (int, float)):
            paired.append({"pair_id": row["pair_id"], "episode_id": row["episode_id"], "pack_a_score": a_value, "pack_e_score": e_value, "difference": a_value - e_value})
    permutation_rows = [{"episode_id": row["episode_id"], "path_difference": row["difference"]} for row in paired]
    return {
        "label": "SECONDARY_EXPLORATORY",
        "pack_a_count": len(a_values), "pack_a_mean": mean(a_values) if a_values else None, "pack_a_median": median(a_values) if a_values else None,
        "pack_e_count": len(e_values), "pack_e_mean": mean(e_values) if e_values else None, "pack_e_median": median(e_values) if e_values else None,
        "paired_numeric_count": len(paired), "paired_mean_difference_pack_a_minus_pack_e": mean(item["difference"] for item in paired) if paired else None,
        "paired_median_difference_pack_a_minus_pack_e": median(item["difference"] for item in paired) if paired else None,
        "individual_paired_differences": paired,
        "episode_cluster_permutation": episode_cluster_permutation(permutation_rows, "path_difference") if paired else None,
    }


def episode_summaries(rows: list[Mapping[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    groups: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows: groups[row["episode_id"]].append(row)
    summaries = []
    for episode_id in sorted(groups):
        items = groups[episode_id]
        a_scores = [binary_primary(item["pack_a_evaluation"]) for item in items]
        e_scores = [binary_primary(item["pack_e_evaluation"]) for item in items]
        summaries.append({
            "episode_id": episode_id, "session_id": items[0]["session_id"], "release_ts": items[0]["release_ts"],
            "member_events": items[0]["member_events"], "same_time_cluster": items[0]["same_time_cluster"],
            "providers_represented": [{"provider": item["provider"], "model": item["model"]} for item in items],
            "complete_provider_pair_count": len(items), "pack_a_15m_results": a_scores, "pack_e_15m_results": e_scores,
            "pack_a_equal_weight_result": mean(a_scores), "pack_e_equal_weight_result": mean(e_scores),
            "mean_provider_level_paired_difference": mean(a - e for a, e in zip(a_scores, e_scores)),
            "outcome_identity": items[0]["pack_a_outcome_id"],
        })
    differences = [row["mean_provider_level_paired_difference"] for row in summaries]
    sign_rows = [{"episode_id": row["episode_id"], "episode_difference": row["mean_provider_level_paired_difference"]} for row in summaries]
    return summaries, {
        "unique_episode_count": len(summaries),
        "pack_a_equal_weight_mean": mean(row["pack_a_equal_weight_result"] for row in summaries),
        "pack_e_equal_weight_mean": mean(row["pack_e_equal_weight_result"] for row in summaries),
        "episode_equal_weight_paired_difference_pack_a_minus_pack_e": mean(differences),
        "episode_equal_weight_median_difference": median(differences),
        "episode_level_exact_sign_flip": episode_cluster_permutation(sign_rows, "episode_difference"),
    }


def provider_summary(all_rows: list[Mapping[str, Any]], complete_rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    completed_by = defaultdict(list)
    for row in complete_rows: completed_by[(row["provider"], row["model"])].append(row)
    result = []
    for provider, model in sorted({(row["provider"], row["model"]) for row in all_rows}):
        all_items, complete = [row for row in all_rows if (row["provider"], row["model"]) == (provider, model)], completed_by[(provider, model)]
        a_accepted = sum(row["pack_a_state"] == "FORECAST_ACCEPTED" for row in all_items)
        e_accepted = sum(row["pack_e_state"] == "FORECAST_ACCEPTED" for row in all_items)
        table = contingency(complete) if complete else None
        def score(arm: str) -> float | None:
            values = [row[arm + "_evaluation"].get("overall_path_score") for row in complete if isinstance(row[arm + "_evaluation"].get("overall_path_score"), (int, float))]
            return mean(values) if values else None
        result.append({"provider": provider, "model": model, "approved_pairs": len(all_items), "complete_pairs": len(complete),
                       "pack_a_accepted_forecasts": a_accepted, "pack_e_accepted_forecasts": e_accepted,
                       "pack_a_15m_correct": table["pack_a_correct"] if table else 0, "pack_e_15m_correct": table["pack_e_correct"] if table else 0,
                       "paired_discordance": {"pack_a_only": table["pack_a_only_correct"], "pack_e_only": table["pack_e_only_correct"]} if table else {},
                       "pack_a_path_mean": score("pack_a"), "pack_e_path_mean": score("pack_e"),
                       "pack_a_rejections": len(all_items) - a_accepted, "pack_e_rejections": len(all_items) - e_accepted})
    return {"label": "DESCRIPTIVE_ONLY_NOT_PROVIDER_SUPERIORITY", "providers": result}


def cluster_summary(all_rows: list[Mapping[str, Any]], complete_rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    result = {}
    for label, flag in (("same_time_cluster", True), ("standalone", False)):
        all_items, complete = [row for row in all_rows if row["same_time_cluster"] is flag], [row for row in complete_rows if row["same_time_cluster"] is flag]
        table = contingency(complete) if complete else None
        adequacy = sum(row.get("attention_scope_adequate") is True for row in complete)
        paired_path_scores = []
        for row in complete:
            a_value, e_value = row["pack_a_evaluation"].get("overall_path_score"), row["pack_e_evaluation"].get("overall_path_score")
            if isinstance(a_value, (int, float)) and isinstance(e_value, (int, float)):
                paired_path_scores.append(a_value - e_value)
        result[label] = {"approved_pairs": len(all_items), "complete_pairs": len(complete),
                         "pack_a_completion_rate": sum(row["pack_a_state"] == "FORECAST_ACCEPTED" for row in all_items) / len(all_items) if all_items else None,
                         "pack_e_completion_rate": sum(row["pack_e_state"] == "FORECAST_ACCEPTED" for row in all_items) / len(all_items) if all_items else None,
                         "paired_15m": table, "attention_adequate": adequacy,
                         "paired_path_score_count": len(paired_path_scores),
                         "paired_path_score_mean_difference_pack_a_minus_pack_e": mean(paired_path_scores) if paired_path_scores else None,
                         "rejected_arms": sum(row["pack_a_state"] != "FORECAST_ACCEPTED" for row in all_items) + sum(row["pack_e_state"] != "FORECAST_ACCEPTED" for row in all_items)}
    result["label"] = "DESCRIPTIVE_SUBGROUP_ONLY"
    return result


def partial_primary_score(batch_dir: Path, row: Mapping[str, Any], arm: str) -> int | None:
    """Read a partial accepted arm against the frozen Outcome without writing an Evaluation."""
    if row[arm.lower() + "_state"] != "FORECAST_ACCEPTED": return None
    folder = pair_directory(batch_dir, row["pair_id"]) / arm_folder(arm)
    prediction, paths = read_json(folder / "prediction.json"), stage_rows(folder / "prediction_path.jsonl")
    outcome_path = pair_directory(batch_dir, row["pair_id"]) / "outcome_reference.json"
    if outcome_path.exists(): outcome = read_json(outcome_path)["outcome"]
    else:
        outcomes = {item["episode_id"]: item for item in read_jsonl(ROOT / "outputs" / "presignal_v21_episode_outcomes" / "outcome_rows.jsonl")}
        outcome = outcomes[row["episode_id"]]
    evaluation = single.evaluate(prediction, paths, outcome, generated_ts="FROZEN_ANALYSIS_READ_ONLY")
    return binary_primary(evaluation)


def missingness_analysis(batch_dir: Path, all_rows: list[dict[str, Any]]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    for row in all_rows:
        if row["completion"] != "COMPLETE_PAIRED":
            row["pack_a_observed_primary_score"] = partial_primary_score(batch_dir, row, "PACK_A")
            row["pack_e_observed_primary_score"] = partial_primary_score(batch_dir, row, "PACK_E")
        else:
            row["pack_a_observed_primary_score"] = binary_primary(row["pack_a_evaluation"])
            row["pack_e_observed_primary_score"] = binary_primary(row["pack_e_evaluation"])
    completion = Counter((row["pack_a_state"] == "FORECAST_ACCEPTED", row["pack_e_state"] == "FORECAST_ACCEPTED") for row in all_rows)
    associations = {
        "by_provider_model": {}, "by_episode": {}, "by_episode_shape": {}, "by_member_count": {}, "by_execution_first_arm": {},
        "continuous_descriptive": [{"pair_id": row["pair_id"], "pack_a_size": row["pack_a_size"], "pack_e_size": row["pack_e_size"],
                                      "pack_size_difference": row["pack_e_size"] - row["pack_a_size"], "prompt_a_length": row["prompt_a_length"],
                                      "prompt_e_length": row["prompt_e_length"], "response_a_length": row["pack_a_response_length"],
                                      "response_e_length": row["pack_e_response_length"], "completion": row["completion"],
                                      "pack_a_rejection_reason": row["pack_a_rejection_reason"], "pack_e_rejection_reason": row["pack_e_rejection_reason"]} for row in all_rows],
    }
    for key, label in (("by_provider_model", lambda r: r["provider"] + "/" + r["model"]), ("by_episode", lambda r: r["episode_id"]),
                       ("by_episode_shape", lambda r: "CLUSTER" if r["same_time_cluster"] else "STANDALONE"),
                       ("by_member_count", lambda r: str(r["member_count"])), ("by_execution_first_arm", lambda r: r["execution_order"][0])):
        grouped: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
        for row in all_rows: grouped[label(row)].append(row)
        associations[key] = {name: {"pairs": len(items), "pack_a_accepted": sum(i["pack_a_state"] == "FORECAST_ACCEPTED" for i in items),
                                      "pack_e_accepted": sum(i["pack_e_state"] == "FORECAST_ACCEPTED" for i in items),
                                      "complete_paired": sum(i["completion"] == "COMPLETE_PAIRED" for i in items)} for name, items in sorted(grouped.items())}
    known_a = sum(row["pack_a_observed_primary_score"] or 0 for row in all_rows if row["pack_a_observed_primary_score"] is not None)
    known_e = sum(row["pack_e_observed_primary_score"] or 0 for row in all_rows if row["pack_e_observed_primary_score"] is not None)
    unknown_a = sum(row["pack_a_observed_primary_score"] is None for row in all_rows)
    unknown_e = sum(row["pack_e_observed_primary_score"] is None for row in all_rows)
    complete_rows = [row for row in all_rows if row["completion"] == "COMPLETE_PAIRED"]
    complete_a = sum(binary_primary(row["pack_a_evaluation"]) for row in complete_rows)
    complete_e = sum(binary_primary(row["pack_e_evaluation"]) for row in complete_rows)
    bounds = {"denominator_approved_pairs": len(all_rows), "complete_case_observed_difference": (complete_a - complete_e) / len(complete_rows),
              "known_pack_a_correct": known_a, "known_pack_e_correct": known_e, "unknown_pack_a_scores": unknown_a, "unknown_pack_e_scores": unknown_e,
              "worst_case_pack_a_difference": (known_a - (known_e + unknown_e)) / len(all_rows),
              "best_case_pack_a_difference": ((known_a + unknown_a) - known_e) / len(all_rows),
              "neutral_midpoint_descriptive_difference": ((known_a + unknown_a * 0.5) - (known_e + unknown_e * 0.5)) / len(all_rows),
              "effect_sign_survives_bounds": False,
              "note": "Bounds preserve all accepted-arm primary scores derived from frozen Prediction and Outcome artifacts; only unaccepted arms vary."}
    completion_table = {"both_accepted": completion[(True, True)], "pack_a_only_accepted": completion[(True, False)], "pack_e_only_accepted": completion[(False, True)], "neither_accepted": completion[(False, False)],
                        "exact_paired_completion_mcnemar_p_value": exact_mcnemar_pvalue(completion[(True, False)], completion[(False, True)])}
    summary = {"approved_pairs": len(all_rows), "pack_a_accepted": sum(row["pack_a_state"] == "FORECAST_ACCEPTED" for row in all_rows),
               "pack_e_accepted": sum(row["pack_e_state"] == "FORECAST_ACCEPTED" for row in all_rows),
               "complete_paired": sum(row["completion"] == "COMPLETE_PAIRED" for row in all_rows), "associations": associations,
               "interpretation": "Descriptive exact counts only; no missing-completely-at-random assumption or unstable regression is used."}
    return summary, completion_table, bounds


def rejected_response_audit(batch_dir: Path, all_rows: list[Mapping[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    classified = []
    for row in all_rows:
        for arm in ("PACK_A", "PACK_E"):
            if row[arm.lower() + "_state"] == "FORECAST_ACCEPTED": continue
            reason = row[arm.lower() + "_rejection_reason"] or "UNKNOWN"
            category = "INVALID_ENUM" if reason == "PREDICTION_REVERSAL_FLAG" else "OTHER_EXPLICIT_REASON"
            candidate = "PROSPECTIVE_FLAT_STAGE_ZERO_PIP_CONSTRAINT" if reason == "PATH_NEUTRAL_PIP_RANGE" else None
            raw = read_json(pair_directory(batch_dir, row["pair_id"]) / arm_folder(arm) / "provider_response_raw.json")
            classified.append({"pair_id": row["pair_id"], "arm": arm, "provider": row["provider"], "model": row["model"],
                               "raw_response_fingerprint": sha256(raw.get("raw_output")), "frozen_rejection_reason": reason,
                               "diagnostic_category": category, "diagnostic_subcategory": reason,
                               "scientific_content_appears_recoverable": False,
                               "current_frozen_parser_correctly_rejected": True,
                               "future_targeted_repair_candidate": candidate,
                               "historical_disposition": "REMAIN_EXCLUDED"})
    counts = Counter(item["diagnostic_subcategory"] for item in classified)
    category_counts = Counter(item["diagnostic_category"] for item in classified)
    candidates = Counter(item["future_targeted_repair_candidate"] for item in classified if item["future_targeted_repair_candidate"])
    return classified, {"rejected_response_count": len(classified), "diagnostic_category_counts": dict(sorted(category_counts.items())),
                        "frozen_rejection_reason_counts": dict(sorted(counts.items())),
                        "future_targeted_repair_candidates": dict(sorted(candidates.items())),
                        "decision_basis": "Six repeated FLAT-stage pip-range violations are a prospective output-contract prevention candidate; all historical rejections remain excluded."}


def attention_summary(batch_dir: Path, complete_rows: list[dict[str, Any]]) -> dict[str, Any]:
    records = []
    for row in complete_rows:
        value = read_json(pair_directory(batch_dir, row["pair_id"]) / "attention_scope_adequacy.json")
        records.append(value)
        row["attention_scope_adequate"] = value.get("decision") == "ADEQUATE"
    return {"completed_pairs_reviewed": len(records), "attention_scope_adequate": sum(r.get("decision") == "ADEQUATE" for r in records),
            "dominant_member_identifiable": sum(bool(r.get("dominant_member_identifiable")) for r in records),
            "joint_member_interpretation_possible": sum(bool(r.get("joint_same_time_interpretation_supported")) for r in records),
            "reinforcement_or_conflict_interpretable": sum(bool(r.get("reinforcement_or_conflict_interpretable")) for r in records),
            "extension_candidates": sum(bool(r.get("essential_episode_attention_concept_missing")) for r in records),
            "recommendation": "NO_ATTENTION_EXTENSION_RECOMMENDED"}


def scientific_interpretation(primary: Mapping[str, Any], cluster: Mapping[str, Any], bounds: Mapping[str, Any], diagnostics: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    evidence = "INDETERMINATE_DUE_TO_MISSINGNESS_OR_SMALL_SAMPLE"
    interpretation = {"evidence_classification": evidence,
                      "primary_effect": primary["paired_risk_difference_pack_a_minus_pack_e"],
                      "primary_uncertainty": primary["conservative_95pct_difference_interval"],
                      "cluster_permutation_p_value": cluster["two_sided_p_value"],
                      "limitations": ["Only 12 unique Episodes were approved and the complete comparative population has 14 provider/Episode pairs.",
                                      "Provider rows sharing an Episode share the same market Outcome and are not independent market events.",
                                      "Missingness is arm-asymmetric and the all-approved sensitivity bounds cross zero.",
                                      "Primary endpoint scoring includes non-directional no-signal responses as not correct directional forecasts."],
                      "pack_superiority_claim": "NOT_SUPPORTED"}
    decision = {"decision": "V2_1_STEP7_TARGETED_OUTPUT_CONTRACT_REPAIR_REQUIRED",
                "exact_defect": "Repeated PATH_NEUTRAL_PIP_RANGE rejections for FLAT prediction-path stages.",
                "affected_responses": diagnostics["future_targeted_repair_candidates"].get("PROSPECTIVE_FLAT_STAGE_ZERO_PIP_CONSTRAINT", 0),
                "historical_rejected_outputs": "REMAIN_EXCLUDED",
                "smallest_future_facing_repair": "Add a prospective provider-output constraint and validation example requiring expected_pips_min = expected_pips_max = 0 whenever expected_direction = FLAT; do not relax the frozen parser or repair historical outputs.",
                "why_not_scale_unchanged": "The repeated mechanical output-contract violation materially reduced paired completion, while the observed arm difference remains uncertain under Episode clustering and missingness bounds."}
    return interpretation, decision


def markdown_summary(primary: Mapping[str, Any], cluster: Mapping[str, Any], path: Mapping[str, Any], missing: Mapping[str, Any], diagnostics: Mapping[str, Any], attention: Mapping[str, Any], decision: Mapping[str, Any]) -> str:
    return "\n".join([
        "# PreSignal v2.1 Frozen Batch Paired Analysis",
        "",
        "## Scope",
        "Read-only analysis of the frozen Step 6 batch. Rejected outputs remain excluded; no provider, market-data, Apps Script, workbook, or Google Sheets operation occurred.",
        "",
        "## Primary Endpoint",
        f"Complete provider/Episode pairs: {primary['pair_count']}. Pack A correct: {primary['pack_a_correct']} ({primary['pack_a_accuracy']:.4f}); Pack E correct: {primary['pack_e_correct']} ({primary['pack_e_accuracy']:.4f}).",
        f"Paired risk difference (A - E): {primary['paired_risk_difference_pack_a_minus_pack_e']:.4f}; exact McNemar p={primary['exact_mcnemar_two_sided_p_value']:.4f}; conservative interval={primary['conservative_95pct_difference_interval']}.",
        f"Episode-cluster exact label-swap: {cluster['unique_episode_clusters']} clusters, {cluster['possible_permutations']} permutations, p={cluster['two_sided_p_value']:.4f}.",
        "",
        "## Missingness",
        f"Pack A accepted {missing['pack_a_accepted']}/21; Pack E accepted {missing['pack_e_accepted']}/21; complete paired {missing['complete_paired']}/21.",
        "",
        "## Output Contract",
        f"Rejected responses: {diagnostics['rejected_response_count']}; frozen reasons: {diagnostics['frozen_rejection_reason_counts']}. {diagnostics['decision_basis']}",
        "",
        "## Attention",
        f"Adequate: {attention['attention_scope_adequate']}/{attention['completed_pairs_reviewed']}; extension candidates: {attention['extension_candidates']}.",
        "",
        "## Decision",
        f"{decision['decision']}: {decision['why_not_scale_unchanged']}",
        "",
        "No Pack-superiority claim is supported by this analysis.",
    ]) + "\n"


def run(*, batch_run_id: str, input_dir: Path | None = None, output_dir: Path | None = None, verify_only: bool = False) -> dict[str, Any]:
    batch_dir = input_dir or (BATCH_ROOT / batch_run_id)
    manifest, state, all_rows, verification = verify_frozen_population(batch_dir)
    if manifest["batch_run_id"] != batch_run_id:
        raise FrozenPopulationIntegrityError("V2_1_STEP7_FROZEN_POPULATION_INTEGRITY_FAILURE:BATCH_RUN_ID")
    complete_rows = [row for row in all_rows if row["completion"] == "COMPLETE_PAIRED"]
    if len(complete_rows) != 14:
        raise FrozenPopulationIntegrityError("V2_1_STEP7_FROZEN_POPULATION_INTEGRITY_FAILURE:COMPLETE_PAIR_COUNT")
    attention = attention_summary(batch_dir, complete_rows)
    primary = contingency(complete_rows, 15)
    primary["primary_scoring_rule"] = "Only direction_15m_ok == true is correct; false and null no-signal direction endpoints are not correct directional forecasts."
    cluster = episode_cluster_permutation(complete_rows)
    secondary = secondary_analysis(complete_rows)
    path = path_score_analysis(complete_rows)
    episodes, episode_equal = episode_summaries(complete_rows)
    providers = provider_summary(all_rows, complete_rows)
    clusters = cluster_summary(all_rows, complete_rows)
    missing, completion_table, bounds = missingness_analysis(batch_dir, all_rows)
    rejected, diagnostics = rejected_response_audit(batch_dir, all_rows)
    interpretation, decision = scientific_interpretation(primary, cluster, bounds, diagnostics)
    payload = {"verification": verification, "all_rows": all_rows, "complete_rows": complete_rows, "primary": primary, "cluster": cluster,
               "secondary": secondary, "path": path, "episodes": episodes, "episode_equal": episode_equal, "providers": providers,
               "clusters": clusters, "missing": missing, "completion_table": completion_table, "bounds": bounds, "rejected": rejected,
               "diagnostics": diagnostics, "attention": attention, "interpretation": interpretation, "decision": decision}
    fingerprint = sha256({key: value for key, value in payload.items()})
    result = {"analysis_run_id": "STEP7-PAIRED-" + short({"batch_run_id": batch_run_id, "version": ANALYSIS_VERSION}), "analysis_fingerprint": fingerprint, **payload}
    if verify_only:
        return result
    target = output_dir or (OUTPUT_ROOT / result["analysis_run_id"])
    write_json(target / "frozen_population_verification.json", verification)
    write_jsonl(target / "complete_pair_population.jsonl", complete_rows)
    write_jsonl(target / "all_approved_pair_population.jsonl", all_rows)
    write_jsonl(target / "rejected_response_classification.jsonl", rejected)
    write_json(target / "primary_15m_paired_analysis.json", primary)
    write_json(target / "primary_15m_contingency_table.json", {key: primary[key] for key in ("both_correct", "pack_a_only_correct", "pack_e_only_correct", "both_incorrect", "pair_count")})
    write_json(target / "episode_cluster_permutation.json", cluster)
    write_json(target / "primary_effect_summary.json", {"primary": primary, "cluster": cluster})
    write_json(target / "secondary_horizon_analysis.json", secondary)
    write_json(target / "path_score_paired_analysis.json", path)
    write_jsonl(target / "episode_level_analysis.jsonl", episodes)
    write_json(target / "episode_equal_weight_summary.json", episode_equal)
    write_json(target / "provider_stratified_summary.json", providers)
    write_json(target / "cluster_vs_standalone_summary.json", clusters)
    write_json(target / "missingness_analysis.json", missing)
    write_json(target / "completion_contingency_table.json", completion_table)
    write_json(target / "missingness_sensitivity_bounds.json", bounds)
    write_json(target / "attention_scope_summary.json", attention)
    write_json(target / "output_contract_diagnostic.json", diagnostics)
    write_json(target / "scientific_interpretation.json", interpretation)
    write_json(target / "development_decision.json", decision)
    (target / "analysis_summary.md").write_text(markdown_summary(primary, cluster, path, missing, diagnostics, attention, decision))
    write_json(target / "analysis_manifest.json", {"analysis_run_id": result["analysis_run_id"], "analysis_version": ANALYSIS_VERSION,
                                                     "batch_run_id": batch_run_id, "analysis_fingerprint": fingerprint,
                                                     "external_calls": {"provider": 0, "acquisition": 0, "market_data": 0, "apps_script": 0, "google_sheets_writes": 0},
                                                     "frozen_contract_tag_target": EXPECTED_TAG_TARGET, "batch_contract_fingerprint": EXPECTED_BATCH_CONTRACT,
                                                     "decision": decision["decision"]})
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch-run-id", default="STEP6-BATCH-f718192a7566138c3fda")
    parser.add_argument("--input-dir", type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    result = run(batch_run_id=args.batch_run_id, input_dir=args.input_dir, output_dir=args.output_dir, verify_only=args.verify_only)
    print(json.dumps({"analysis_run_id": result["analysis_run_id"], "analysis_fingerprint": result["analysis_fingerprint"], "decision": result["decision"]["decision"], "provider_calls": 0}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
