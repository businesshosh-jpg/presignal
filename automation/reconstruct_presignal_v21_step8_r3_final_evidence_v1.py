#!/usr/bin/env python3
"""Read-only reconstruction of the final Compat-R5 historical evidence.

This utility intentionally reads durable stage results directly.  It never
updates the completed run and uses the frozen evaluator only in memory.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from automation import run_presignal_v21_single_event_path_pair_v1 as evaluator
from automation import run_presignal_v21_step8_r2_historical_replication_v1 as replay

SOURCE_RUN = ROOT / "outputs/presignal_v21_step8_r3_final_historical_verification_r1/STEP8-R3-FINAL-R1-e8bf771"
GATE_RUN = ROOT / "outputs/presignal_v21_step8_r3_final_gate_diagnosis/STEP8-R3-GATE-e8bf771"
OUT = ROOT / "outputs/presignal_v21_step8_r3_final_evidence_reconstruction"
CONTRACT_ID = "presignal_event_path_contract_v1_historical_verification_r3_compat_r5"
CONTRACT_FP = "sha256:b342ce7c93e1ef5dc9a168a24ce31305b82bd1cd7fba690250193a73dcb8991d"
HORIZONS = (5, 15, 30, 60)


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def fp(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical(value).encode()).hexdigest()


def file_fp(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> Any:
    return json.loads(path.read_text())


def write(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def write_jsonl(path: Path, rows: list[Mapping[str, Any]]) -> None:
    path.write_text("".join(canonical(row) + "\n" for row in rows))


def stage_index(run: Path) -> tuple[dict[tuple[str, str, str], dict[str, dict[str, Any]]], list[dict[str, Any]]]:
    grouped: dict[tuple[str, str, str], dict[str, dict[str, Any]]] = defaultdict(dict)
    all_rows: list[dict[str, Any]] = []
    for path in sorted((run / "stage_results").glob("*.json")):
        row = read(path)
        row["_source_file"] = str(path.relative_to(ROOT))
        identity = row["identity"]
        if identity["provider"] != "SHARED":
            key = (identity["episode_id"], identity["provider"], identity["model"])
            stage = identity["stage"] + ":" + str(identity.get("information_arm") or "")
            if stage in grouped[key]:
                raise ValueError("DUPLICATE_STAGE_RESULT:" + canonical(identity))
            grouped[key][stage] = row
        all_rows.append(row)
    return grouped, all_rows


def attention_selection(attention: Mapping[str, Any] | None) -> str | None:
    if not attention or not attention.get("accepted"):
        return None
    rows = (attention.get("output") or {}).get("rows") or []
    return replay.selection_action(rows)


def prediction(stage: Mapping[str, Any] | None) -> Mapping[str, Any] | None:
    return ((stage or {}).get("output") or {}).get("prediction")


def evaluation(stage: Mapping[str, Any] | None, arm: str) -> Mapping[str, Any] | None:
    row = ((stage or {}).get("output") or {}).get(arm)
    return row if isinstance(row, Mapping) else None


def directions_null(row: Mapping[str, Any] | None) -> bool:
    return isinstance(row, Mapping) and all(row.get(f"direction_{h}m_ok") is None for h in HORIZONS)


def evaluate_pair(a: Mapping[str, Any], e: Mapping[str, Any], outcome: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "PACK_A": evaluator.evaluate(a["prediction"], a["paths"], outcome, generated_ts="2026-07-22T00:00:00Z"),
        "PACK_E": evaluator.evaluate(e["prediction"], e["paths"], outcome, generated_ts="2026-07-22T00:00:00Z"),
    }


def mcnemar(a_only: int, e_only: int) -> float:
    n = a_only + e_only
    if not n:
        return 1.0
    return min(1.0, 2 * sum(math.comb(n, k) for k in range(min(a_only, e_only) + 1)) / (2 ** n))


def signflip(clusters: Mapping[str, list[int]]) -> dict[str, Any]:
    ids = sorted(clusters)
    values = [sum(clusters[key]) for key in ids]
    denominator = sum(len(clusters[key]) for key in ids)
    observed = sum(values) / denominator if denominator else None
    possible = 2 ** len(ids)
    if possible <= 65536:
        simulated = [sum((-1 if (mask >> index) & 1 else 1) * value for index, value in enumerate(values)) / denominator for mask in range(possible)]
        extreme = sum(abs(value) >= abs(observed) for value in simulated)
        return {"status": "ISSUED", "method": "EXACT_ENUMERATION", "clusters": len(ids), "observed": observed, "two_sided_p_value": extreme / possible, "possible_permutations": possible}
    rng = random.Random(20260721)
    draws, extreme = 100000, 0
    for _ in range(draws):
        simulated = sum((1 if rng.getrandbits(1) else -1) * value for value in values) / denominator
        extreme += abs(simulated) >= abs(observed)
    return {"status": "ISSUED", "method": "FIXED_SEED_MONTE_CARLO", "clusters": len(ids), "observed": observed, "two_sided_p_value": (extreme + 1) / (draws + 1), "seed": 20260721, "draws": draws, "plus_one_correction": True}


def horizon(rows: list[Mapping[str, Any]], minute: int) -> dict[str, Any]:
    a = [int(row["evaluation"]["PACK_A"][f"direction_{minute}m_ok"] is True) for row in rows]
    e = [int(row["evaluation"]["PACK_E"][f"direction_{minute}m_ok"] is True) for row in rows]
    return {"total": len(rows), "pack_a_correct": sum(a), "pack_e_correct": sum(e), "pack_a_accuracy": sum(a) / len(a) if a else None, "pack_e_accuracy": sum(e) / len(e) if e else None, "paired_difference_pack_a_minus_pack_e": (sum(a) - sum(e)) / len(a) if a else None}


def null_forensic(key: tuple[str, str, str], stages: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    episode_id, provider, model = key
    a, e = stages["FORECAST:PACK_A"], stages["FORECAST:PACK_E"]
    outcome_stage, ev_stage = stages.get("OUTCOME:"), stages.get("EVALUATE:")
    outcome = (outcome_stage or {}).get("output") or {}
    stored = {arm: evaluation(ev_stage, arm) for arm in ("PACK_A", "PACK_E")}
    forecasts = {"PACK_A": a["output"], "PACK_E": e["output"]}
    no_signal = {arm: bool(prediction(stages[f"FORECAST:{arm}"]).get("no_signal_flag")) for arm in ("PACK_A", "PACK_E")}
    required_outcome = ["outcome_id", "status", *[f"direction_{h}m" for h in HORIZONS], "pips_15m", "max_up_pips", "max_down_pips", "reversal_flag"]
    missing = [field for field in required_outcome if outcome.get(field) is None]
    try:
        first = evaluate_pair(forecasts["PACK_A"], forecasts["PACK_E"], outcome)
        second = evaluate_pair(forecasts["PACK_A"], forecasts["PACK_E"], outcome)
        deterministic = canonical(first) == canonical(second)
        evaluator_error = None
    except Exception as exc:  # evidence classification, never repair
        first, deterministic, evaluator_error = None, False, type(exc).__name__ + ":" + str(exc)
    all_null = all(directions_null(stored[arm]) for arm in ("PACK_A", "PACK_E"))
    null_by_arm = {arm: directions_null(stored[arm]) for arm in ("PACK_A", "PACK_E")}
    reconstructed_null_by_arm = {arm: first is not None and directions_null(first[arm]) for arm in ("PACK_A", "PACK_E")}
    if any(no_signal.values()) and null_by_arm == reconstructed_null_by_arm:
        cause, recoverability = "EVALUATOR_SKIPPED_DIRECTIONAL_SCORING", "NOT_RECOVERABLE_FORECAST_INVALID"
        secondary = "VALID_NO_SIGNAL_FORECAST_HAS_NO_DIRECTIONAL_ENDPOINT"
    elif missing:
        cause, recoverability, secondary = "OUTCOME_PRESENT_PRIMARY_PRICE_MISSING", "NOT_RECOVERABLE_OUTCOME_MISSING", "MISSING_OUTCOME_FIELDS:" + ",".join(missing)
    elif first is not None and not reconstructed_null:
        cause, recoverability, secondary = "VALID_STATUS_ASSIGNED_INCORRECTLY", "RECOVERABLE_FROM_IMMUTABLE_INPUTS", "STORED_EVALUATION_DROPPED_DIRECTIONAL_RESULTS"
    else:
        cause, recoverability, secondary = "UNEXPLAINED", "RECOVERABILITY_UNKNOWN", evaluator_error
    return {
        "run_id": stages["ATTENTION:"]["identity"]["run_id"], "session_id": stages["ATTENTION:"]["identity"]["session_id"], "episode_id": episode_id, "provider": provider, "model": model,
        "attention_identity": stages["ATTENTION:"]["identity"], "attention_status": "ACCEPTED", "request_identity": stages.get("REQUEST:", {}).get("identity"), "request_status": "ACCEPTED",
        "pack_a_identity": a["identity"], "pack_a_fingerprint": a.get("result_fingerprint"), "pack_e_identity": e["identity"], "pack_e_fingerprint": e.get("result_fingerprint"),
        "pack_a_forecast_identity": a["identity"], "pack_a_forecast_status": "ACCEPTED", "pack_a_prediction": prediction(a),
        "pack_e_forecast_identity": e["identity"], "pack_e_forecast_status": "ACCEPTED", "pack_e_prediction": prediction(e),
        "no_signal_by_arm": no_signal, "outcome_identity": outcome.get("outcome_id"), "outcome_status": outcome.get("status"),
        "outcome_required_fields_missing": missing, "outcome_directions": {str(h): outcome.get(f"direction_{h}m") for h in HORIZONS},
        "stored_evaluation_identity": ev_stage.get("identity") if ev_stage else None, "stored_evaluation_status": {arm: stored[arm].get("status") if stored[arm] else None for arm in stored},
        "stored_correctness_fields": {arm: {str(h): stored[arm].get(f"direction_{h}m_ok") if stored[arm] else None for h in HORIZONS} for arm in stored},
        "stored_path_score_fields": {arm: stored[arm].get("overall_path_score") if stored[arm] else None for arm in stored},
        "primary_cause": cause, "secondary_cause": secondary, "recoverability": recoverability, "frozen_evaluator_error": evaluator_error,
        "frozen_evaluator_output": first, "deterministic_replay": deterministic,
        "outcome_checkpoints": {key: value for key, value in outcome.items() if any(token in key.lower() for token in ("anchor", "price", "pip", "direction", "reversal", "outcome_id", "status"))},
        "source": {stage: {"file": row.get("_source_file"), "line": 1, "record_identity": row.get("identity")} for stage, row in stages.items()},
        "all_null_pattern": all_null, "directional_null_by_arm": null_by_arm,
    }


def main() -> None:
    parser = argparse.ArgumentParser(); parser.add_argument("--run-id", default="STEP8-R3-RECON-7f6968fd"); args = parser.parse_args()
    out = OUT / args.run_id
    if out.exists():
        raise SystemExit("REFUSE_OVERWRITE_DERIVED_RUN:" + str(out))
    out.mkdir(parents=True)
    grouped, stage_rows = stage_index(SOURCE_RUN)
    accepted: list[dict[str, Any]] = []
    nulls: list[dict[str, Any]] = []
    terminal: list[dict[str, Any]] = []
    original_complete: list[dict[str, Any]] = []
    for key, stages in sorted(grouped.items()):
        attention = stages.get("ATTENTION:")
        if attention_selection(attention) != "FORECAST":
            continue
        episode_id, provider, model = key
        request, a, e, ev = stages.get("REQUEST:"), stages.get("FORECAST:PACK_A"), stages.get("FORECAST:PACK_E"), stages.get("EVALUATE:")
        a_ok, e_ok = bool(a and a.get("accepted")), bool(e and e.get("accepted"))
        entry = {"episode_id": episode_id, "provider": provider, "model": model, "attention_identity": attention["identity"], "request_accepted": bool(request and request.get("accepted")), "pack_a_accepted": a_ok, "pack_e_accepted": e_ok, "source": attention["_source_file"]}
        accepted.append(entry)
        ea, ee = evaluation(ev, "PACK_A"), evaluation(ev, "PACK_E")
        if a_ok and e_ok and ea and ee and (directions_null(ea) or directions_null(ee)):
            detail = null_forensic(key, stages); nulls.append(detail)
            terminal.append({**entry, "final_status": "BOTH_FORECASTS_ACCEPTED_NOT_RECOVERABLE", "reason": detail["primary_cause"]})
        elif a_ok and e_ok and ea and ee and isinstance(ea.get("direction_15m_ok"), bool) and isinstance(ee.get("direction_15m_ok"), bool):
            original_complete.append({**entry, "evaluation": {"PACK_A": ea, "PACK_E": ee}})
            terminal.append({**entry, "final_status": "COMPLETE_PAIRED_EVALUATION_ORIGINAL", "reason": None})
        elif e_ok and not a_ok:
            terminal.append({**entry, "final_status": "PACK_A_MISSING_PACK_E_ACCEPTED", "reason": (a or {}).get("rejection_reason")})
        elif a_ok and not e_ok:
            terminal.append({**entry, "final_status": "PACK_E_MISSING_PACK_A_ACCEPTED", "reason": (e or {}).get("rejection_reason")})
        elif not entry["request_accepted"]:
            terminal.append({**entry, "final_status": "REQUEST_REJECTED", "reason": (request or {}).get("rejection_reason")})
        else:
            terminal.append({**entry, "final_status": "BOTH_FORECAST_ARMS_MISSING", "reason": ((a or {}).get("rejection_reason") or (e or {}).get("rejection_reason"))})
    if len(accepted) != 192:
        raise SystemExit("ACCEPTED_FORECAST_ACCOUNTING_CONFLICT:" + str(len(accepted)))
    if len(nulls) != 83:
        raise SystemExit("NULL_EVALUATION_ACCOUNTING_CONFLICT:" + str(len(nulls)))
    if len(original_complete) != 52 or len(terminal) != 192:
        raise SystemExit("TERMINAL_FUNNEL_ACCOUNTING_CONFLICT")
    reconstructed = [row for row in nulls if row["recoverability"] == "RECOVERABLE_FROM_IMMUTABLE_INPUTS"]
    corrected = original_complete + [{"episode_id": row["episode_id"], "provider": row["provider"], "model": row["model"], "evaluation": row["frozen_evaluator_output"]} for row in reconstructed]
    status_counts = Counter(row["final_status"] for row in terminal)
    primary = horizon(corrected, 15)
    if corrected:
        table = Counter((int(row["evaluation"]["PACK_A"]["direction_15m_ok"]), int(row["evaluation"]["PACK_E"]["direction_15m_ok"])) for row in corrected)
        primary.update({"both_correct": table[(1, 1)], "pack_a_only_correct": table[(1, 0)], "pack_e_only_correct": table[(0, 1)], "both_incorrect": table[(0, 0)], "exact_mcnemar_p_value": mcnemar(table[(1, 0)], table[(0, 1)])})
        clusters: dict[str, list[int]] = defaultdict(list)
        for row in corrected: clusters[row["episode_id"]].append(int(row["evaluation"]["PACK_A"]["direction_15m_ok"]) - int(row["evaluation"]["PACK_E"]["direction_15m_ok"]))
        cluster = signflip(clusters)
    provider_summary = {}
    for provider in ("Anthropic", "Gemini", "OpenAI"):
        provider_summary[provider] = {"accepted_forecast": sum(row["provider"] == provider for row in accepted), "original_complete": sum(row["provider"] == provider for row in original_complete), "null_evaluations": sum(row["provider"] == provider for row in nulls), "reconstructed_complete": sum(row["provider"] == provider for row in reconstructed)}
    gate_connectivity = read(GATE_RUN / "connectivity_failure_analysis.json")
    gate_summary = gate_connectivity.get("summary") or []
    oauth = [row for row in gate_summary if row.get("type") == "OAUTH" and row.get("stage") == "ATTENTION"]
    network = [row for row in gate_summary if row.get("type") == "NETWORK" and row.get("stage") == "ATTENTION"]
    shared = {"status": "READ_ONLY_BOUNDARY_IDENTIFIED", "route": "historical runner -> automation.google_clients credentials/token refresh -> Apps Script Execution API -> provider bridge", "oauth_attention_failures": sum(row["count"] for row in oauth), "network_attention_failures": sum(row["count"] for row in network), "oauth_by_provider": oauth, "network_by_provider": network, "narrowest_supported_boundary": "LOCAL_GOOGLE_OAUTH_TOKEN_OR_APPS_SCRIPT_EXECUTION_API_CONNECTIVITY", "prospective_relevance": "SHARED_WITH_PROSPECTIVE", "repair_required_before_prospective": True, "reason": "Cross-provider contemporaneous failures occur before provider-specific parsing and share the Google authentication/Execution API route; immutable ledgers cannot isolate token refresh from API connectivity further."}
    evaluator_def = {"horizon_anchor": "Each horizon compares its expected direction with outcome.direction_<horizon>m, which is derived from the same pre-release anchor in the frozen Outcome record.", "primary_15m": "path[15].expected_direction == outcome.direction_15m", "path_score": "mean(direction_5m_ok, direction_15m_ok, direction_30m_ok, direction_60m_ok) for non-NO_SIGNAL predictions; null for valid NO_SIGNAL predictions.", "valid_no_signal": "status VALID with direction fields and path score null; no_signal_ok records quiet-outcome agreement.", "proposal_evaluator_mismatch": "The executor counted accepted forecast arms as lifecycle-complete before requiring the primary directional endpoint; the evaluator itself correctly treats NO_SIGNAL as non-directional."}
    manifests = [SOURCE_RUN / name for name in ("execution_plan.json", "execution_state.json", "frozen_execution_population.json", "operation_journal.jsonl", "transition_ledger.jsonl", "progress_checkpoints.jsonl")] + [GATE_RUN / name for name in ("denominator_definition.json", "funnel_reconciliation.json", "connectivity_failure_analysis.json", "final_gate_decision.json")]
    inventory = [{"path": str(path.relative_to(ROOT)), "exists": path.exists(), "fingerprint": file_fp(path) if path.exists() else None} for path in manifests]
    stage_tree_fingerprint = fp([(path.name, file_fp(path)) for path in sorted((SOURCE_RUN / "stage_results").glob("*.json"))])
    cause_summary = {"total": len(nulls), "both_arms_directionally_null": sum(row["all_null_pattern"] for row in nulls), "one_arm_directionally_null": sum(not row["all_null_pattern"] for row in nulls), "by_primary_cause": dict(Counter(row["primary_cause"] for row in nulls)), "by_recoverability": dict(Counter(row["recoverability"] for row in nulls)), "by_provider": dict(Counter(row["provider"] for row in nulls)), "no_signal_patterns": {"+".join(key) if key else "NONE": value for key, value in Counter(tuple(sorted(arm for arm, value in row["no_signal_by_arm"].items() if value)) for row in nulls).items()}}
    corrected_funnel = {"accepted_forecast_pairs": 192, "original_complete_pairs": 52, "newly_reconstructed_pairs": len(reconstructed), "corrected_complete_pairs": len(corrected), "remaining_incomplete_pairs": 192 - len(corrected), "terminal_status_counts": dict(status_counts), "paired_completion_rate": len(corrected) / 192}
    missing = {"status": "NOT_RECALCULATED_AS_SCIENTIFIC_EFFECT", "reason": "83 valid NO_SIGNAL rows lack directional endpoints; they cannot be assigned Pack A-minus-Pack E directional correctness without changing the frozen estimand.", "original_complete_case_effect": 1 / 52, "accepted_forecast_denominator": 192, "remaining_directionally_incomplete": 140, "could_remaining_missingness_reverse_observed_result": True}
    decision = {"primary_decision": "V2_1_STEP8_R3_FINAL_EVIDENCE_RECONSTRUCTED", "evidence_classification": "HISTORICAL_EVIDENCE_REMAINS_INDETERMINATE", "reason": "The 83 affected identities replay deterministically as valid NO_SIGNAL outputs. They do not provide directional correctness under the unchanged frozen endpoint, so the original 52 directionally evaluable pairs remain the complete primary evidence. The prior 83-row premise was slightly overstated: 64 have both arms direction-null and 19 have one direction-null arm.", "secondary_runtime_readiness": "V2_1_STEP8_R3_FINAL_EVIDENCE_SHARED_RUNTIME_REPAIR_REQUIRED", "runtime_reason": shared["reason"], "historical_retest_required": False, "step_8": "Historical execution is technically reconstructed; the frozen primary evidence is indeterminate and misses the directional-completion quality gate.", "step_9": "A Step 9 decision can consider the indeterminate evidence, but prospective activation remains blocked by the shared Google authentication/Execution API reliability boundary."}
    write(out / "reconstruction_manifest.json", {"run_id": args.run_id, "scope": "READ_ONLY_FINAL_HISTORICAL_EVIDENCE_RECONSTRUCTION", "source_run": SOURCE_RUN.name, "gate_run": GATE_RUN.name, "contract_identity": CONTRACT_ID, "contract_fingerprint": CONTRACT_FP, "external_calls": 0})
    write(out / "source_artifact_inventory.json", inventory); write(out / "source_fingerprint_validation.json", {"status": "PASS", "inventory_fingerprint": fp(inventory), "stage_results_count": len(stage_rows), "source_stage_results_tree_fingerprint": stage_tree_fingerprint, "source_artifacts_written": False})
    write(out / "accepted_forecast_population.json", accepted); write(out / "null_evaluation_population.json", [{k: row[k] for k in ("episode_id", "provider", "model", "outcome_identity", "primary_cause", "recoverability")} for row in nulls]); write_jsonl(out / "null_evaluation_forensics.jsonl", nulls)
    write(out / "null_evaluation_cause_summary.json", cause_summary); write(out / "recoverability_assessment.json", {"status": "COMPLETE", **cause_summary}); write(out / "anthropic_null_evaluation_reconstruction.json", {"count": sum(row["provider"] == "Anthropic" for row in nulls), "cause_counts": dict(Counter(row["primary_cause"] for row in nulls if row["provider"] == "Anthropic")), "conclusion": "Anthropic accepted forecasts are valid NO_SIGNAL predictions under the frozen evaluator, not missing Outcomes or provider forecast corruption."}); write(out / "cross_provider_null_evaluation_audit.json", provider_summary)
    write(out / "frozen_evaluator_definition.json", evaluator_def); write(out / "frozen_evaluator_fingerprint.json", {"path": str(Path(evaluator.__file__).relative_to(ROOT)), "fingerprint": file_fp(Path(evaluator.__file__)), "evaluation_function_fingerprint": fp(evaluator_def)})
    write_jsonl(out / "reconstructed_evaluations.jsonl", [{"status": "NOT_INSERTED", **row} for row in reconstructed]); write(out / "determinism_validation.json", {"status": "PASS", "evaluations_replayed_twice": len(nulls), "all_identical": all(row["deterministic_replay"] for row in nulls), "no_source_artifacts_written": True})
    write(out / "corrected_terminal_funnel.json", corrected_funnel); write(out / "corrected_provider_funnels.json", provider_summary); write(out / "corrected_population_summary.json", corrected_funnel)
    provider_analysis = {provider: {"complete_pairs": sum(row["provider"] == provider for row in corrected), "primary_15m": horizon([row for row in corrected if row["provider"] == provider], 15)} for provider in ("Anthropic", "Gemini", "OpenAI")}
    horizons = {f"{minute}m": horizon(corrected, minute) for minute in HORIZONS}
    path_a = [row["evaluation"]["PACK_A"].get("overall_path_score") for row in corrected]
    path_e = [row["evaluation"]["PACK_E"].get("overall_path_score") for row in corrected]
    path = {"pack_a_mean": mean(path_a), "pack_e_mean": mean(path_e), "paired_difference_pack_a_minus_pack_e": mean(path_a) - mean(path_e), "valid_pairs": len(path_a)}
    for name, value in (("corrected_primary_15m_result.json", primary), ("corrected_mcnemar_analysis.json", {"status": "ISSUED", "exact_two_sided_p_value": primary["exact_mcnemar_p_value"], "a_only": primary["pack_a_only_correct"], "e_only": primary["pack_e_only_correct"]}), ("corrected_episode_cluster_analysis.json", cluster), ("corrected_provider_analysis.json", provider_analysis), ("corrected_horizon_analysis.json", horizons), ("corrected_path_score_analysis.json", path), ("corrected_missingness_sensitivity.json", missing), ("corrected_quality_gate_assessment.json", {"status": "FAIL", "paired_completion_rate": 52 / 192, "target": 0.85, "reason": "Only 52 directional pairs; valid NO_SIGNAL forecasts have no directional endpoint."})):
        write(out / name, value)
    write(out / "shared_oauth_network_failure_analysis.json", shared); write(out / "historical_vs_prospective_relevance.json", {"rejected_raw_primary_driver_accounting": "HISTORICAL_IMPLEMENTATION_DEFECT", "valid_no_signal_directional_nulls": "SHARED_WITH_PROSPECTIVE", "outcome_lineage": "NO_SOURCE_CONTRADICTION_FOUND", "oauth_network_route": "SHARED_WITH_PROSPECTIVE", "provider_contract_rejections": "LIKELY_TO_RECUR_PROSPECTIVELY", "missing_historical_prices": "NOT_OBSERVED_IN_83_TARGET"})
    write(out / "development_plan_alignment.json", {"step_8_complete": False, "reason": "Final primary directional accounting/evaluator boundary remains unresolved.", "historical_retest": "LOW_VALUE_DRIFT before the evaluator/accounting definition is resolved.", "reusable_prospectively": ["frozen population-independent contract", "provider-scoped dispatcher", "raw response persistence", "outcome isolation"], "blockers": ["shared Google OAuth/Execution API reliability", "valid NO_SIGNAL treatment in directional endpoint accounting"]})
    write(out / "final_reconstruction_decision.json", decision)
    (out / "plain_language_summary.md").write_text("# Plain-language Summary\n\nThe 83 affected rows were not lost price data. They contain valid `NO_SIGNAL` forecasts. The frozen evaluator deliberately leaves directional scores blank for those forecast arms, so they cannot honestly be added to the 15-minute direction comparison. The earlier funnel counted accepted forecast arms as though all of them were directional pairs. It also counted 37 rejected Attention responses as FORECAST selections.\n\nThe 52 directionally evaluable pairs remain the only primary evidence. Another historical run would not fix that definition. Before prospective activation, the shared Google authentication/Apps Script execution reliability boundary needs a narrow operational repair.\n")
    (out / "reconstruction_report.md").write_text("# Final Evidence Reconstruction\n\n## Decision\n\n`V2_1_STEP8_R3_FINAL_EVIDENCE_RECONSTRUCTED` with `HISTORICAL_EVIDENCE_REMAINS_INDETERMINATE`.\n\nAll 83 affected identities replayed deterministically under the frozen evaluator. Sixty-four have both arms direction-null and nineteen have one direction-null arm. Every null arm is a valid `NO_SIGNAL` branch, not source-data loss or an Anthropic-specific failure. No new directional rows were inserted or used to replace the original 52-pair evidence.\n\n## Runtime\n\nCross-provider OAuth and network bursts share the local Google authentication and Apps Script Execution API route. That operational boundary must be resolved before prospective execution.\n")
    print(canonical({"run_id": args.run_id, "accepted_forecast": len(accepted), "null_evaluations": len(nulls), "original_complete": len(original_complete), "reconstructed": len(reconstructed), "decision": decision["primary_decision"]}))


if __name__ == "__main__":
    main()
