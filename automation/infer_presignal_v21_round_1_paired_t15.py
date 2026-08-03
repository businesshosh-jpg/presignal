#!/usr/bin/env python3
"""Local, append-only paired T+15 inference over accepted Round 1 rows."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "outputs" / "presignal_v21_full_round_1_forecast_execution"
AGGREGATE_DIR = BASE / "PPHB-R1-ROUND-1-AGGREGATE-EVALUATION-RESULT-20260804T050000Z"
FINAL_REPORT_DIR = BASE / "PPHB-R1-ROUND-1-FINAL-REPORT-20260804T060000Z"
ROWS_PATH = AGGREGATE_DIR / "aggregate_per_forecast_rows.jsonl"
METRICS_PATH = AGGREGATE_DIR / "aggregate_metrics.json"
AUTH_ID = "PPHB-R1-PAIRED-T15-INFERENCE-AUTHORIZATION-20260804T070000Z"
TEST_SPECIFICATION = {
    "endpoint": "T+15 directional accuracy",
    "population": "Frozen common paired-scoreable observations only",
    "null_hypothesis": "Among discordant pairs, Pack A-correct/Pack E-incorrect and Pack A-incorrect/Pack E-correct outcomes are equally likely.",
    "alternative_hypothesis": "The discordant outcome probabilities differ between Pack A and Pack E.",
    "test": "Exact two-sided McNemar binomial test",
    "calculation": "Two times the lower binomial tail under p=0.5, capped at 1.0; no continuity correction.",
    "direction": "two-sided",
    "alpha": 0.05,
    "ties": "Both-correct and both-incorrect pairs do not enter the McNemar test statistic; they remain in the reported four-cell table.",
    "reporting_precision": "Exact stored float; six decimals for display.",
    "confidence_interval": "Not authorized because no canonical paired risk-difference interval method and confidence level are governed.",
    "interpretation_boundary": "The test concerns this frozen Round 1 paired population only; it does not authorize causal, provider-selection, replacement, or future-performance claims.",
}


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical(value).encode()).hexdigest()


def file_digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text())


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text("".join(canonical(row) + "\n" for row in rows))


def reconstruct_pairs() -> list[dict[str, Any]]:
    grouped: defaultdict[tuple[str, str, str, str, str], dict[str, dict[str, Any]]] = defaultdict(dict)
    for row in read_jsonl(ROWS_PATH):
        required = {"slice_id", "episode_id", "outcome_id", "provider", "model", "forecast_call_id", "pack", "no_signal", "t15_correct"}
        if not required <= set(row):
            raise ValueError("PAIRED_ROW_SCHEMA_CONFLICT")
        if row["pack"] not in {"PACK_A", "PACK_E"}:
            raise ValueError("PAIRED_PACK_LINEAGE_CONFLICT")
        key = (row["slice_id"], row["episode_id"], row["outcome_id"], row["provider"], row["model"])
        if row["pack"] in grouped[key]:
            raise ValueError("DUPLICATE_PAIRED_ARM:" + row["forecast_call_id"])
        grouped[key][row["pack"]] = row
    pairs = []
    for key, arms in sorted(grouped.items()):
        if set(arms) != {"PACK_A", "PACK_E"}:
            raise ValueError("INCOMPLETE_PAIRED_SCOREABLE_IDENTITY:" + ":".join(key))
        a, e = arms["PACK_A"], arms["PACK_E"]
        # A common paired-scoreable observation requires both arms to issue a signal.
        if a["no_signal"] or e["no_signal"]:
            continue
        if a["t15_correct"] not in {True, False} or e["t15_correct"] not in {True, False}:
            raise ValueError("PAIRED_T15_SCOREABILITY_CONFLICT")
        pairs.append({
            "slice_id": key[0], "episode_id": key[1], "outcome_id": key[2], "provider": key[3], "model": key[4],
            "pack_a_forecast_call_id": a["forecast_call_id"], "pack_e_forecast_call_id": e["forecast_call_id"],
            "pack_a_t15_correct": a["t15_correct"], "pack_e_t15_correct": e["t15_correct"],
            "scoreability_proof": "Both accepted aggregate rows have no_signal=false and boolean T+15 correctness under the same accepted Outcome.",
        })
    if len(pairs) != 206:
        raise ValueError("PAIRED_POPULATION_COUNT_CONFLICT:" + str(len(pairs)))
    if len({item["pack_a_forecast_call_id"] for item in pairs}) != 206 or len({item["pack_e_forecast_call_id"] for item in pairs}) != 206:
        raise ValueError("PAIRED_FORECAST_IDENTITY_DUPLICATE")
    return pairs


def exact_two_sided_mcnemar(a_only: int, e_only: int) -> float:
    discordant = a_only + e_only
    if not discordant:
        return 1.0
    return min(1.0, 2 * sum(math.comb(discordant, k) for k in range(min(a_only, e_only) + 1)) / (2 ** discordant))


def freeze_authorization(path: Path) -> dict[str, Any]:
    pairs = reconstruct_pairs()
    authorization = {
        "authorization_id": AUTH_ID,
        "authorization_schema_version": "1.0.0",
        "authorization_status": "ACTIVE_SINGLE_USE",
        "source_aggregate_artifact": {"id": AGGREGATE_DIR.name, "aggregate_rows_sha256": file_digest(ROWS_PATH), "aggregate_metrics_sha256": file_digest(METRICS_PATH)},
        "source_final_report_artifact": {"id": FINAL_REPORT_DIR.name, "scientific_interpretation_sha256": file_digest(FINAL_REPORT_DIR / "scientific_interpretation.json")},
        "exact_pair_population": {"pairs": 206, "pair_inventory_sha256": digest(pairs), "pack_a_correct": 86, "pack_e_correct": 100, "descriptive_difference_a_minus_e": -0.06796116504854371},
        "test_specification": TEST_SPECIFICATION,
        "permitted_outputs": ["four_cell_correctness_table", "discordant_pair_counts", "paired_risk_difference", "exact_two_sided_mcnemar_p_value", "restrained_interpretation"],
        "not_authorized": ["confidence_interval", "provider_inference", "subgroup_tests", "multiple_comparison_adjustment", "odds_ratio", "bayesian_analysis", "power_analysis", "composite_score", "forecast_or_outcome_change"],
        "external_limits": {"provider_calls": 0, "apps_script_reads": 0, "market_data_calls": 0, "google_reads": 0, "google_writes": 0, "outcome_attachment": 0, "retries": 0},
        "single_use_resume_rule": "Execution may use only this exact authorization and the unchanged accepted aggregate row artifact; completed evidence may not be recomputed or replaced.",
    }
    authorization["authorization_fingerprint"] = digest(authorization)
    write_json(path, authorization)
    return authorization


def load_authorization(path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    authorization = read_json(path)
    fingerprint = authorization.pop("authorization_fingerprint", None)
    if fingerprint != digest(authorization):
        raise ValueError("INFERENCE_AUTHORIZATION_TAMPER_CONFLICT")
    authorization["authorization_fingerprint"] = fingerprint
    if authorization.get("authorization_status") != "ACTIVE_SINGLE_USE" or authorization.get("authorization_id") != AUTH_ID:
        raise ValueError("INFERENCE_AUTHORIZATION_NOT_ACTIVE")
    if authorization.get("test_specification") != TEST_SPECIFICATION:
        raise ValueError("INFERENCE_TEST_SPECIFICATION_CONFLICT")
    if any(value != 0 for value in authorization.get("external_limits", {}).values()):
        raise ValueError("INFERENCE_EXTERNAL_LIMIT_CONFLICT")
    pairs = reconstruct_pairs()
    population = authorization.get("exact_pair_population", {})
    if population.get("pairs") != len(pairs) or population.get("pair_inventory_sha256") != digest(pairs):
        raise ValueError("INFERENCE_PAIR_POPULATION_BINDING_CONFLICT")
    if authorization["source_aggregate_artifact"]["aggregate_rows_sha256"] != file_digest(ROWS_PATH):
        raise ValueError("INFERENCE_AGGREGATE_ARTIFACT_BINDING_CONFLICT")
    return authorization, pairs


def analyze(pairs: list[dict[str, Any]]) -> dict[str, Any]:
    table = Counter((pair["pack_a_t15_correct"], pair["pack_e_t15_correct"]) for pair in pairs)
    both_correct = table[(True, True)]
    a_only = table[(True, False)]
    e_only = table[(False, True)]
    both_incorrect = table[(False, False)]
    if sum((both_correct, a_only, e_only, both_incorrect)) != 206:
        raise ValueError("FOUR_CELL_COUNT_CONFLICT")
    a_correct = both_correct + a_only
    e_correct = both_correct + e_only
    if (a_correct, e_correct) != (86, 100):
        raise ValueError("ACCEPTED_CORRECTNESS_TOTAL_CONFLICT")
    p_value = exact_two_sided_mcnemar(a_only, e_only)
    return {
        "four_cell_table": {"both_correct": both_correct, "pack_a_correct_pack_e_incorrect": a_only, "pack_a_incorrect_pack_e_correct": e_only, "both_incorrect": both_incorrect},
        "discordant_pairs": {"pack_a_only_correct": a_only, "pack_e_only_correct": e_only, "total": a_only + e_only},
        "paired_risk_difference_a_minus_e": (a_correct - e_correct) / len(pairs),
        "pack_a_correct": a_correct,
        "pack_e_correct": e_correct,
        "exact_two_sided_mcnemar_p_value": p_value,
        "pre_specified_alpha": TEST_SPECIFICATION["alpha"],
        "null_rejected_at_pre_specified_alpha": p_value < TEST_SPECIFICATION["alpha"],
    }


def execute(authorization_path: Path, result_dir: Path) -> dict[str, Any]:
    if result_dir.exists():
        raise ValueError("INFERENCE_RESULT_ALREADY_EXISTS")
    authorization, pairs = load_authorization(authorization_path)
    result = analyze(pairs)
    result_dir.mkdir(parents=True)
    write_json(result_dir / "inference_run_manifest.json", {"run_id": result_dir.name, "authorization_id": authorization["authorization_id"], "authorization_fingerprint": authorization["authorization_fingerprint"], "external_operations": 0, "metric_recalculation": False})
    write_jsonl(result_dir / "paired_t15_inventory.jsonl", pairs)
    write_json(result_dir / "pair_population_proof.json", {"pair_count": len(pairs), "pair_inventory_sha256": digest(pairs), "duplicate_pairs": 0, "unresolved_pairs": 0, "excluded_no_signal_or_non_scoreable_records": 106, "same_outcome_required": True})
    write_json(result_dir / "test_specification.json", TEST_SPECIFICATION)
    write_json(result_dir / "paired_t15_inference.json", result)
    interpretation = {
        "decision": "ROUND_1_PAIRED_T15_INFERENCE_COMPLETE",
        "descriptive_difference": "Pack A-E paired risk difference is %.6f." % result["paired_risk_difference_a_minus_e"],
        "inferential_result": "Exact two-sided McNemar p-value is %.6f under the pre-specified alpha=0.05 threshold." % result["exact_two_sided_mcnemar_p_value"],
        "conclusion": "The pre-specified null is rejected for this frozen paired T+15 population." if result["null_rejected_at_pre_specified_alpha"] else "The pre-specified null is not rejected for this frozen paired T+15 population.",
        "evidence_strength": "INFERENTIAL_EVIDENCE_FOR_FROZEN_PAIRED_T15_DIFFERENCE" if result["null_rejected_at_pre_specified_alpha"] else "MODERATE_DESCRIPTIVE_EVIDENCE_WITHOUT_INFERENTIAL_SUPPORT",
        "boundary": "This result does not establish causality, universal superiority, provider selection validity, Pack A replacement, future performance, or Immediate Impulse improvement.",
        "recommendation": "Keep Pack E as a hypothesis-supported arm and Pack A as the baseline; the smallest next Move is a separately authorized confirmatory prospective Round 2 protocol, not replacement.",
        "analyses_not_performed": authorization["not_authorized"],
    }
    write_json(result_dir / "restrained_interpretation.json", interpretation)
    write_json(result_dir / "inference_decision.json", {"decision": "ROUND_1_PAIRED_T15_INFERENCE_COMPLETE", "authorization_status": "COMPLETED", "confidence_interval": "NOT_CALCULATED_METHOD_NOT_AUTHORIZED", "external_operations": 0, "new_metrics": 0, "interpretation": interpretation})
    return {"authorization": authorization, "result": result, "interpretation": interpretation}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--freeze-authorization", type=Path)
    parser.add_argument("--authorization", type=Path)
    parser.add_argument("--result-dir", type=Path)
    args = parser.parse_args()
    if bool(args.freeze_authorization) == bool(args.authorization):
        raise SystemExit("CHOOSE_EXACTLY_ONE_OPERATION")
    if args.freeze_authorization:
        if args.freeze_authorization.exists():
            raise SystemExit("INFERENCE_AUTHORIZATION_ALREADY_EXISTS")
        authorization = freeze_authorization(args.freeze_authorization)
        print(json.dumps({"authorization_id": authorization["authorization_id"], "authorization_fingerprint": authorization["authorization_fingerprint"]}, sort_keys=True))
        return 0
    if args.result_dir is None:
        raise SystemExit("RESULT_DIR_REQUIRED")
    outcome = execute(args.authorization, args.result_dir)
    print(json.dumps({"decision": outcome["interpretation"]["decision"], "p_value": outcome["result"]["exact_two_sided_mcnemar_p_value"], "four_cells": outcome["result"]["four_cell_table"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
