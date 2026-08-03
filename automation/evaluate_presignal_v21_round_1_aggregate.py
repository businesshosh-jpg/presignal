#!/usr/bin/env python3
"""Append-only aggregate evaluator for accepted prospective Round 1 Slice rows."""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from statistics import mean
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "outputs" / "presignal_v21_full_round_1_forecast_execution"
STAGE_DIR = BASE / "PPHB-R1-PROSPECTIVE-OUTCOME-EVALUATION-STAGE-COMPLETION-20260804T040000Z"
STAGE_RECONCILIATION = STAGE_DIR / "stage_completion_reconciliation.json"
BOUNDARY = STAGE_DIR / "aggregate_evaluation_authorization_boundary.json"
METRICS = [
    "T+15 directional accuracy",
    "Immediate Impulse directional accuracy",
    "magnitude or pip error",
    "horizon accuracy",
    "path accuracy",
    "reversal accuracy",
]
SLICE_EVALUATIONS = {
    "SLICE-002": "PPHB-R1-OUTCOME-EVALUATE-SLICE-002-20260803T045628Z-5b2104c5270c",
    "SLICE-003": "PPHB-R1-OUTCOME-EVALUATION-SLICE-003-PAIRED-EXCLUSION-20260803T081500Z-1a04811ea2b95396242c-v2",
    "SLICE-004": "PPHB-R1-OUTCOME-EVALUATE-SLICE-004-20260803T083241Z-0ccd2ce593a5",
    "SLICE-005": "PPHB-R1-OUTCOME-EVALUATE-SLICE-005-PAIRED-EXCLUSION-20260803T091100Z-7dc7040e7eefe6766505",
    "SLICE-006": "PPHB-R1-OUTCOME-EVALUATE-SLICE-006-20260803T090526Z-4b6396c50c92",
    "SLICE-007": "PPHB-R1-OUTCOME-EVALUATE-SLICE-007-20260803T094016Z-81c3d79659cc",
    "SLICE-008": "PPHB-R1-OUTCOME-EVALUATE-SLICE-008-20260803T101555Z-b162981a8f90",
    "SLICE-009": "PPHB-R1-OUTCOME-EVALUATE-SLICE-009-20260803T103200Z-af38aa3c6a26",
    "SLICE-010": "PPHB-R1-OUTCOME-EVALUATE-SLICE-010-20260803T104301Z-a2340f9b9a1a",
    "SLICE-011": "PPHB-R1-OUTCOME-EVALUATE-SLICE-011-20260803T110347Z-b56ebc7495bf",
    "SLICE-012": "PPHB-R1-OUTCOME-EVALUATE-SLICE-012-20260803T112356Z-c68c116427d5",
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


def artifact_inventory() -> list[dict[str, Any]]:
    inventory = []
    for slice_id, run_id in SLICE_EVALUATIONS.items():
        run_dir = BASE / run_id
        decision_path = run_dir / "evaluation_decision.json"
        rows_path = run_dir / "per_forecast_evaluation_rows.jsonl"
        if not decision_path.exists() or not rows_path.exists():
            raise ValueError("MISSING_ACCEPTED_SLICE_EVALUATION_ARTIFACT:" + slice_id)
        decision = read_json(decision_path)
        if decision.get("decision") != "OUTCOME_" + slice_id.replace("-", "_") + "_MINIMAL_EVALUATION_COMPLETE":
            raise ValueError("SLICE_EVALUATION_DECISION_CONFLICT:" + slice_id)
        if decision.get("metrics") != METRICS or decision.get("composite_score") != "NOT_CALCULATED_NOT_AUTHORIZED":
            raise ValueError("SLICE_METRIC_ALLOW_LIST_CONFLICT:" + slice_id)
        inventory.append({
            "slice_id": slice_id,
            "evaluation_run_id": run_id,
            "evaluation_decision_sha256": file_digest(decision_path),
            "per_forecast_rows_sha256": file_digest(rows_path),
        })
    return inventory


def freeze_authorization(path: Path) -> dict[str, Any]:
    stage = read_json(STAGE_RECONCILIATION)
    if stage["forecast_records_evaluated"] != 518 or stage["evaluated_complete_pairs"] != 259:
        raise ValueError("STAGE_COMPLETION_POPULATION_CONFLICT")
    authorization = {
        "authorization_id": "PPHB-R1-AGGREGATE-EVALUATION-AUTHORIZATION-20260804T050000Z",
        "authorization_schema_version": "1.0.0",
        "authorization_status": "ACTIVE_SINGLE_USE",
        "move_type": "ROUND_1_AGGREGATE_EVALUATION",
        "stage_completion_artifact": {
            "id": STAGE_DIR.name,
            "sha256": file_digest(STAGE_RECONCILIATION),
        },
        "authorization_boundary_sha256": file_digest(BOUNDARY),
        "accepted_slice_artifacts": artifact_inventory(),
        "population": {
            "evaluation_records": 518,
            "pack_a_records": 259,
            "pack_e_records": 259,
            "complete_pack_a_e_pairs": 259,
            "attached_outcomes": 138,
            "paired_excluded_unavailable_episodes": 10,
            "authority_attention_lineage_excluded_episodes": 3,
            "terminal_invalid_forecasts": 3,
        },
        "permitted_metrics": METRICS,
        "primary_endpoint": "T+15 directional accuracy",
        "secondary_measurement": "Immediate Impulse directional accuracy",
        "aggregation_rule": "Identity-level record-pooled aggregation from accepted per-forecast Slice rows; never average Slice percentages.",
        "directional_denominator_rule": "Exclude valid no-signal forecasts from directional, magnitude, path, and reversal denominators; FLAT is correct only on exact equality.",
        "immediate_impulse_rule": "Strict-score only rows with immediate_supported=true; APPROXIMATION_ONLY remains not applicable.",
        "paired_comparison_rule": "Use only matching same-episode/provider/model Pack A/E rows where both arms are scoreable for that metric.",
        "rounding_rule": "Store exact ratios and means; display to six decimals in reports.",
        "prohibited": ["external_access", "outcome_attachment", "google_operations", "retries", "composite_score", "statistical_inference", "provider_selection", "subgroup_mining"],
        "external_limits": {"provider_calls": 0, "apps_script_reads": 0, "market_data_requests": 0, "google_reads": 0, "google_writes": 0, "retries": 0, "outcome_attachment": 0},
        "single_use_resume_rule": "May resume only from this exact append-only authorization and accepted aggregate artifacts; no input artifact may be replaced.",
    }
    authorization["authorization_fingerprint"] = digest(authorization)
    write_json(path, authorization)
    return authorization


def load_and_validate(authorization_path: Path) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    authorization = read_json(authorization_path)
    fingerprint = authorization.pop("authorization_fingerprint", None)
    if fingerprint != digest(authorization):
        raise ValueError("AGGREGATE_AUTHORIZATION_TAMPER_OR_FINGERPRINT_CONFLICT")
    authorization["authorization_fingerprint"] = fingerprint
    if authorization.get("authorization_status") != "ACTIVE_SINGLE_USE":
        raise ValueError("AGGREGATE_AUTHORIZATION_NOT_ACTIVE")
    if authorization.get("permitted_metrics") != METRICS:
        raise ValueError("AGGREGATE_METRIC_ALLOW_LIST_CONFLICT")
    if authorization.get("external_limits") != {"provider_calls": 0, "apps_script_reads": 0, "market_data_requests": 0, "google_reads": 0, "google_writes": 0, "retries": 0, "outcome_attachment": 0}:
        raise ValueError("AGGREGATE_EXTERNAL_LIMIT_CONFLICT")
    inventory = artifact_inventory()
    if authorization.get("accepted_slice_artifacts") != inventory:
        raise ValueError("AGGREGATE_SLICE_ARTIFACT_BINDING_CONFLICT")
    rows: list[dict[str, Any]] = []
    sources: list[dict[str, Any]] = []
    seen_calls: set[str] = set()
    for item in inventory:
        path = BASE / item["evaluation_run_id"] / "per_forecast_evaluation_rows.jsonl"
        slice_rows = read_jsonl(path)
        for row in slice_rows:
            required = {"forecast_call_id", "episode_id", "pack", "provider", "model", "outcome_id", "no_signal", "immediate_supported", "t15_correct", "h5_correct", "h15_correct", "h30_correct", "h60_correct", "magnitude_interval_error_pips", "magnitude_midpoint_error_pips", "path_score", "reversal_correct"}
            if not required <= set(row):
                raise ValueError("AGGREGATE_ROW_SCHEMA_CONFLICT:" + item["slice_id"])
            if row["forecast_call_id"] in seen_calls:
                raise ValueError("DUPLICATE_EVALUATION_FORECAST_IDENTITY:" + row["forecast_call_id"])
            if row["pack"] not in {"PACK_A", "PACK_E"}:
                raise ValueError("PACK_LINEAGE_CONFLICT:" + row["forecast_call_id"])
            seen_calls.add(row["forecast_call_id"])
            rows.append({**row, "slice_id": item["slice_id"]})
        sources.append({"slice_id": item["slice_id"], "row_count": len(slice_rows), "rows_sha256": item["per_forecast_rows_sha256"]})
    if len(rows) != 518 or {row["pack"] for row in rows} != {"PACK_A", "PACK_E"}:
        raise ValueError("AGGREGATE_RECORD_POPULATION_CONFLICT")
    counts = {pack: sum(row["pack"] == pack for row in rows) for pack in ("PACK_A", "PACK_E")}
    if counts != {"PACK_A": 259, "PACK_E": 259}:
        raise ValueError("AGGREGATE_PACK_POPULATION_CONFLICT")
    return authorization, rows, sources


def ratio(numerator: int, denominator: int) -> float | None:
    return None if not denominator else numerator / denominator


def metric_summary(rows: list[dict[str, Any]], pack: str) -> dict[str, Any]:
    eligible = [row for row in rows if not row["no_signal"]]
    def accuracy(key: str) -> dict[str, Any]:
        return {"numerator": sum(row[key] is True for row in eligible), "denominator": len(eligible), "result": ratio(sum(row[key] is True for row in eligible), len(eligible)), "excluded_no_signal": len(rows) - len(eligible)}
    impulse = [row for row in eligible if row["immediate_supported"]]
    magnitudes = [row["magnitude_interval_error_pips"] for row in eligible]
    midpoints = [row["magnitude_midpoint_error_pips"] for row in eligible]
    paths = [row["path_score"] for row in eligible]
    return {
        "pack": pack,
        "evaluation_records": len(rows),
        "no_signal_excluded_from_directional_metrics": len(rows) - len(eligible),
        "T+15 directional accuracy": accuracy("t15_correct"),
        "Immediate Impulse directional accuracy": {"numerator": sum(row["immediate_correct"] is True for row in impulse), "denominator": len(impulse), "result": ratio(sum(row["immediate_correct"] is True for row in impulse), len(impulse)), "status": "NOT_APPLICABLE_STRICT" if not impulse else "STRICT_SCORED", "excluded_approximation_or_no_signal": len(rows) - len(impulse)},
        "magnitude or pip error": {"denominator": len(magnitudes), "mean_interval_distance_error_pips": mean(magnitudes), "mean_midpoint_absolute_error_pips": mean(midpoints), "excluded_no_signal": len(rows) - len(magnitudes)},
        "horizon accuracy": {str(h): accuracy(f"h{h}_correct") for h in (5, 15, 30, 60)},
        "path accuracy": {"denominator": len(paths), "result": mean(paths), "excluded_no_signal": len(rows) - len(paths)},
        "reversal accuracy": accuracy("reversal_correct"),
    }


def pair_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    pairs: defaultdict[tuple[str, str, str, str], dict[str, dict[str, Any]]] = defaultdict(dict)
    for row in rows:
        pairs[(row["episode_id"], row["outcome_id"], row["provider"], row["model"])][row["pack"]] = row
    if len(pairs) != 259 or any(set(arms) != {"PACK_A", "PACK_E"} for arms in pairs.values()):
        raise ValueError("AGGREGATE_PAIRED_IDENTITY_CONFLICT")
    t15 = [arms for arms in pairs.values() if not arms["PACK_A"]["no_signal"] and not arms["PACK_E"]["no_signal"]]
    return {
        "complete_pairs": len(pairs),
        "common_paired_t15_scoreable": len(t15),
        "pack_a_t15_numerator": sum(arms["PACK_A"]["t15_correct"] is True for arms in t15),
        "pack_e_t15_numerator": sum(arms["PACK_E"]["t15_correct"] is True for arms in t15),
        "pack_a_t15_result": ratio(sum(arms["PACK_A"]["t15_correct"] is True for arms in t15), len(t15)),
        "pack_e_t15_result": ratio(sum(arms["PACK_E"]["t15_correct"] is True for arms in t15), len(t15)),
        "difference_a_minus_e": ratio(sum(arms["PACK_A"]["t15_correct"] is True for arms in t15), len(t15)) - ratio(sum(arms["PACK_E"]["t15_correct"] is True for arms in t15), len(t15)),
        "interpretation": "Descriptive common-pair comparison only; no significance, confidence intervals, winner selection, or generalization.",
    }


def execute(authorization_path: Path, run_dir: Path) -> dict[str, Any]:
    if run_dir.exists():
        raise ValueError("AGGREGATE_RUN_ALREADY_EXISTS")
    authorization, rows, sources = load_and_validate(authorization_path)
    by_pack = {pack: [row for row in rows if row["pack"] == pack] for pack in ("PACK_A", "PACK_E")}
    metrics = {pack: metric_summary(by_pack[pack], pack) for pack in by_pack}
    pairs = pair_summary(rows)
    run_dir.mkdir(parents=True)
    write_json(run_dir / "aggregate_run_manifest.json", {"run_id": run_dir.name, "authorization_id": authorization["authorization_id"], "authorization_fingerprint": authorization["authorization_fingerprint"], "source_slice_count": len(sources), "external_operations": 0, "outcome_attachment_operations": 0, "metrics": METRICS})
    write_json(run_dir / "accepted_slice_artifact_inventory.json", {"slice_artifacts": authorization["accepted_slice_artifacts"], "source_rows": sources})
    write_json(run_dir / "identity_population_proof.json", {"evaluation_record_count": len(rows), "evaluation_record_sha256": digest(rows), "unique_forecast_call_ids": len({row["forecast_call_id"] for row in rows}), "pack_counts": {pack: len(by_pack[pack]) for pack in by_pack}, "unique_episodes": len({row["episode_id"] for row in rows}), "duplicate_evaluation_identities": 0, "terminal_invalid_or_excluded_records_included": 0})
    write_jsonl(run_dir / "aggregate_per_forecast_rows.jsonl", rows)
    write_json(run_dir / "aggregate_metrics.json", {"aggregation_method": authorization["aggregation_rule"], "rounding": authorization["rounding_rule"], "PACK_A": metrics["PACK_A"], "PACK_E": metrics["PACK_E"], "paired_comparison": pairs})
    write_json(run_dir / "aggregate_decision.json", {"decision": "ROUND_1_AGGREGATE_EVALUATION_COMPLETE", "primary_endpoint": "T+15 directional accuracy", "secondary_measurement": "Immediate Impulse directional accuracy", "immediate_impulse_status": {pack: metrics[pack]["Immediate Impulse directional accuracy"]["status"] for pack in metrics}, "composite_score": "NOT_CALCULATED_NOT_AUTHORIZED", "analyses_not_authorized": ["statistical significance", "confidence intervals", "hypothesis tests", "provider selection", "meta-forecast performance", "subgroup mining", "post-hoc optimization", "composite score"], "external_operations": 0})
    write_json(run_dir / "round_1_completion_reconciliation.json", {"decision": "ROUND_1_AGGREGATE_EVALUATION_COMPLETE", "authorization_status": "COMPLETED", "evaluation_records": len(rows), "pack_a_records": len(by_pack["PACK_A"]), "pack_e_records": len(by_pack["PACK_E"]), "complete_pairs": pairs["complete_pairs"], "unresolved_identities": 0, "duplicate_evaluation_identities": 0, "external_operations": 0, "outcome_modifications": 0})
    return {"authorization": authorization, "metrics": metrics, "pairs": pairs, "sources": sources}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--freeze-authorization", type=Path)
    parser.add_argument("--authorization", type=Path)
    parser.add_argument("--run-id")
    args = parser.parse_args()
    if bool(args.freeze_authorization) == bool(args.authorization):
        raise SystemExit("CHOOSE_EXACTLY_ONE_OPERATION")
    if args.freeze_authorization:
        if args.freeze_authorization.exists():
            raise SystemExit("AGGREGATE_AUTHORIZATION_ALREADY_EXISTS")
        authorization = freeze_authorization(args.freeze_authorization)
        print(json.dumps({"authorization_id": authorization["authorization_id"], "authorization_fingerprint": authorization["authorization_fingerprint"]}, sort_keys=True))
        return 0
    if not args.run_id:
        raise SystemExit("RUN_ID_REQUIRED")
    result = execute(args.authorization, BASE / args.run_id)
    print(json.dumps({"decision": "ROUND_1_AGGREGATE_EVALUATION_COMPLETE", "pack_a_t15": result["metrics"]["PACK_A"]["T+15 directional accuracy"], "pack_e_t15": result["metrics"]["PACK_E"]["T+15 directional accuracy"], "common_pairs": result["pairs"]["common_paired_t15_scoreable"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
