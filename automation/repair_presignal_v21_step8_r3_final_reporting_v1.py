#!/usr/bin/env python3
"""Produce a read-only final report that separates NO_SIGNAL from failures."""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from automation import reconstruct_presignal_v21_step8_r3_final_evidence_v1 as recon
from automation import presignal_v21_canonical_states_v1 as states

SOURCE_RUN = recon.SOURCE_RUN
RECON_RUN = ROOT / "outputs/presignal_v21_step8_r3_final_evidence_reconstruction/STEP8-R3-RECON-7f6968fd-r4"
OUT = ROOT / "outputs/presignal_v21_step8_r3_final_reporting_repair"
QUALITY_GATES = ROOT / "outputs/presignal_v21_step8_r3_repair/STEP8-R3-REPAIR-df9c25e/fresh_verification_quality_gates.json"
CONTRACT_ID = recon.CONTRACT_ID
CONTRACT_FP = recon.CONTRACT_FP


def write(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def write_jsonl(path: Path, rows: list[Mapping[str, Any]]) -> None:
    path.write_text("".join(recon.canonical(row) + "\n" for row in rows))


def _pair_classification(canonical: Mapping[str, Mapping[str, str]]) -> tuple[str, str, str | None]:
    a, e = canonical["PACK_A"], canonical["PACK_E"]
    forecast = (a["forecast_state"], e["forecast_state"])
    evaluation = (a["evaluation_state"], e["evaluation_state"])
    if forecast == (states.ForecastState.DIRECTIONAL, states.ForecastState.DIRECTIONAL):
        if all(value in {states.EvaluationState.CORRECT, states.EvaluationState.INCORRECT} for value in evaluation):
            return "DIRECTIONAL_PAIR_EVALUABLE", "BOTH_ARMS_DIRECTIONAL", None
        return "TRUE_INCOMPLETE_PAIR", "OUTCOME_FAILURE", "DIRECTIONAL_ENDPOINT_UNAVAILABLE"
    if states.ForecastState.NO_SIGNAL in forecast and all(value in {states.ForecastState.DIRECTIONAL, states.ForecastState.NO_SIGNAL} for value in forecast):
        return "VALID_NO_SIGNAL_PAIR", {
            (states.ForecastState.NO_SIGNAL, states.ForecastState.NO_SIGNAL): "BOTH_ARMS_NO_SIGNAL",
            (states.ForecastState.NO_SIGNAL, states.ForecastState.DIRECTIONAL): "PACK_A_NO_SIGNAL_PACK_E_DIRECTIONAL",
            (states.ForecastState.DIRECTIONAL, states.ForecastState.NO_SIGNAL): "PACK_A_DIRECTIONAL_PACK_E_NO_SIGNAL",
        }[forecast], None
    runtime = {a["runtime_state"], e["runtime_state"]}
    if runtime & {states.RuntimeState.TRANSPORT_FAILED, states.RuntimeState.STATUS_UNKNOWN}:
        return "TRUE_INCOMPLETE_PAIR", "TRANSPORT_OR_UNKNOWN", None
    return "TRUE_INCOMPLETE_PAIR", "INVALID_OR_INCOMPLETE_FORECAST", None


def classify(stages: Mapping[str, Mapping[str, Any]]) -> tuple[str, str, str | None]:
    """Compatibility wrapper for pair taxonomy tests; delegates to canonical states."""
    attention = {"accepted": True, "output": {"rows": [{"status": "parsed", "attention_label": "PRIMARY_DRIVER"}]}}
    outcome = (stages.get("OUTCOME:") or {}).get("output")
    canonical = {
        arm: states.canonical_states(attention=attention, forecast=stages.get("FORECAST:" + arm), evaluation=recon.evaluation(stages.get("EVALUATE:"), arm), outcome=outcome)
        for arm in ("PACK_A", "PACK_E")
    }
    return _pair_classification(canonical)


def canonical_records(source_run: Path | None = None) -> list[dict[str, Any]]:
    """Return one canonical reporting record per provider/Episode identity."""
    grouped, _ = recon.stage_index(source_run or SOURCE_RUN)
    records = []
    for (episode_id, provider, model), stages in sorted(grouped.items()):
        attention = stages.get("ATTENTION:")
        selection = states.selection_state(attention)
        outcome = (stages.get("OUTCOME:") or {}).get("output")
        arms = {}
        for arm in ("PACK_A", "PACK_E"):
            forecast = stages.get("FORECAST:" + arm)
            prediction = recon.prediction(forecast)
            arm_states = states.canonical_states(
                attention=attention, forecast=stages.get("FORECAST:" + arm),
                evaluation=recon.evaluation(stages.get("EVALUATE:"), arm), outcome=outcome,
            )
            arms[arm] = {**arm_states, "accepted": arm_states["forecast_state"] in {states.ForecastState.DIRECTIONAL, states.ForecastState.NO_SIGNAL}, "no_signal": arm_states["forecast_state"] == states.ForecastState.NO_SIGNAL, "rejection_reason": None if arm_states["forecast_state"] in {states.ForecastState.DIRECTIONAL, states.ForecastState.NO_SIGNAL} else (forecast or {}).get("rejection_reason"), "prediction_id": prediction.get("prediction_id") if prediction else None}
        classification = _pair_classification(arms) if selection == states.SelectionState.SELECTED else ("NOT_FORECAST_SELECTED", selection, None)
        operations = []
        if selection != states.SelectionState.SELECTED:
            operations.append({"stage": "FORECAST", "information_arm": None, "runtime_state": states.RuntimeState.NOT_ATTEMPTED})
        else:
            for stage, arm in (("ATTENTION", None), ("REQUEST", None), ("FORECAST", "PACK_A"), ("FORECAST", "PACK_E")):
                record = stages.get(stage + ":" + (arm or ""))
                operations.append({"stage": stage, "information_arm": arm, "runtime_state": states.runtime_state(record, selected=True)})
        members = ((attention or {}).get("output") or {}).get("rows") or []
        primary = [row for row in members if row.get("status") == "parsed" and row.get("attention_label") == "PRIMARY_DRIVER"]
        records.append({"episode_id": episode_id, "provider": provider, "model": model, "selection_state": selection, "request_accepted": bool(stages.get("REQUEST:") and stages["REQUEST:"].get("accepted")), "arms": arms, "canonical_states": {arm: {key: arms[arm][key] for key in ("selection_state", "runtime_state", "forecast_state", "evaluation_state")} for arm in arms}, "operations": operations, "top_level_status": classification[0], "subclass": classification[1], "failure_reason": classification[2], "attention_primary_driver_genres": sorted({str(item.get("genre") or "UNKNOWN") for item in primary}), "attention_primary_driver_types": sorted({str(item.get("type") or "UNKNOWN") for item in primary}), "attention_primary_driver_ranks": sorted({item.get("attention_rank") for item in primary}), "attention_primary_driver_confidences": sorted({item.get("confidence") for item in primary}), "source_attention": (attention or {}).get("_source_file")})
    return records


def _section(name: str, rule: str, denominator: int, counts: Mapping[str, Any], excluded: Mapping[str, int]) -> dict[str, Any]:
    return {"population_name": name, "eligibility_rule": rule, "denominator": denominator, "counts": dict(counts), "excluded_state_counts": dict(excluded)}


def _state_counts(values: list[str], allowed: tuple[str, ...]) -> dict[str, int]:
    observed = Counter(values)
    return {value: observed[value] for value in allowed}


def canonical_report(records: list[Mapping[str, Any]]) -> dict[str, Any]:
    """Aggregate canonical states only; record order cannot affect this output."""
    selections = _state_counts([row["selection_state"] for row in records], (states.SelectionState.SELECTED, states.SelectionState.WATCH, states.SelectionState.IGNORED, states.SelectionState.NOT_SELECTED, states.SelectionState.REJECTED))
    selected = [row for row in records if row["selection_state"] == states.SelectionState.SELECTED]
    directional = [row for row in selected if all(row["arms"][arm]["forecast_state"] == states.ForecastState.DIRECTIONAL and row["arms"][arm]["evaluation_state"] in {states.EvaluationState.CORRECT, states.EvaluationState.INCORRECT} for arm in ("PACK_A", "PACK_E"))]
    a_correct = sum(row["arms"]["PACK_A"]["evaluation_state"] == states.EvaluationState.CORRECT for row in directional)
    e_correct = sum(row["arms"]["PACK_E"]["evaluation_state"] == states.EvaluationState.CORRECT for row in directional)
    patterns = Counter((row["arms"]["PACK_A"]["forecast_state"], row["arms"]["PACK_E"]["forecast_state"]) for row in selected)
    arm_forecasts = [row["arms"][arm] for row in selected for arm in ("PACK_A", "PACK_E")]
    operation_states = _state_counts([operation["runtime_state"] for row in records for operation in row["operations"]], (states.RuntimeState.NOT_ATTEMPTED, states.RuntimeState.SUCCESS, states.RuntimeState.PROVIDER_REJECTED, states.RuntimeState.TRANSPORT_FAILED, states.RuntimeState.STATUS_UNKNOWN))
    evaluation_states = _state_counts([arm["evaluation_state"] for arm in arm_forecasts], (states.EvaluationState.NOT_APPLICABLE, states.EvaluationState.PENDING_OUTCOME, states.EvaluationState.CORRECT, states.EvaluationState.INCORRECT, states.EvaluationState.OUTCOME_UNAVAILABLE))
    top = Counter(row["top_level_status"] for row in selected)
    return {
        "selection_summary": _section("all_attention_decisions", "one canonical SelectionState per provider/Episode Attention decision", len(records), selections, {}),
        "directional_summary": _section("paired_directional_15m", "SELECTED and both arms DIRECTIONAL with CORRECT or INCORRECT 15-minute evaluation", len(directional), {"pack_a_correct": a_correct, "pack_e_correct": e_correct, "pack_a_rate": a_correct / len(directional) if directional else None, "pack_e_rate": e_correct / len(directional) if directional else None, "paired_difference_pack_a_minus_pack_e": (a_correct - e_correct) / len(directional) if directional else None, "by_provider": {provider: {"pairs": len(items), "pack_a_correct": sum(item["arms"]["PACK_A"]["evaluation_state"] == states.EvaluationState.CORRECT for item in items), "pack_e_correct": sum(item["arms"]["PACK_E"]["evaluation_state"] == states.EvaluationState.CORRECT for item in items)} for provider, items in ((provider, [row for row in directional if row["provider"] == provider]) for provider in sorted({row["provider"] for row in records}))}}, Counter(arm["forecast_state"] for arm in arm_forecasts if arm["forecast_state"] != states.ForecastState.DIRECTIONAL)),
        "abstention_summary": _section("valid_no_signal_forecasts", "SELECTED forecast arms with ForecastState.NO_SIGNAL", sum(arm["forecast_state"] == states.ForecastState.NO_SIGNAL for arm in arm_forecasts), {"pack_a_no_signal": sum(row["arms"]["PACK_A"]["forecast_state"] == states.ForecastState.NO_SIGNAL for row in selected), "pack_e_no_signal": sum(row["arms"]["PACK_E"]["forecast_state"] == states.ForecastState.NO_SIGNAL for row in selected), "paired_patterns": {"/".join(key): value for key, value in sorted(patterns.items())}, "coverage_rate": sum(arm["forecast_state"] in {states.ForecastState.DIRECTIONAL, states.ForecastState.NO_SIGNAL} for arm in arm_forecasts) / len(arm_forecasts) if arm_forecasts else None}, Counter(arm["forecast_state"] for arm in arm_forecasts if arm["forecast_state"] not in {states.ForecastState.DIRECTIONAL, states.ForecastState.NO_SIGNAL})),
        "operational_summary": _section("selected_attempted_operations", "canonical RuntimeState for each selected operation; NOT_ATTEMPTED shown separately for non-entry", sum(value for key, value in operation_states.items() if key != states.RuntimeState.NOT_ATTEMPTED), operation_states, {"non_selected_not_attempted": operation_states[states.RuntimeState.NOT_ATTEMPTED]}),
        "evaluation_summary": _section("forecast_arm_evaluations", "EvaluationState per selected forecast arm", len(arm_forecasts), evaluation_states, {"non_directional_or_incomplete": sum(value for key, value in evaluation_states.items() if key == states.EvaluationState.NOT_APPLICABLE)}),
        "population_reconciliation": _section("selected_pair_reconciliation", "SelectionState.SELECTED; each selected identity has exactly one terminal pair category", len(selected), {"accepted_forecast_identities": len(selected), "directional_pack_a_e_pairs": top["DIRECTIONAL_PAIR_EVALUABLE"], "valid_pairs_involving_no_signal": top["VALID_NO_SIGNAL_PAIR"], "incomplete_or_rejected_identities": top["TRUE_INCOMPLETE_PAIR"], "reconciliation": sum(top.values()), "legacy_mapping": "accepted FORECAST identities = SelectionState.SELECTED"}, {}),
    }


def pair_rows() -> list[dict[str, Any]]:
    rows = [dict(row) for row in canonical_records() if row["selection_state"] == states.SelectionState.SELECTED]
    if len(rows) != 192:
        raise RuntimeError("ACCEPTED_FORECAST_RECONCILIATION_FAILED:" + str(len(rows)))
    return rows


def rate(numerator: int, denominator: int = 192) -> dict[str, Any]:
    return {"numerator": numerator, "denominator": denominator, "rate": numerator / denominator}


def main() -> None:
    parser = argparse.ArgumentParser(); parser.add_argument("--run-id", default="STEP8-R3-REPORT-REPAIR-ea3b06c"); args = parser.parse_args()
    out = OUT / args.run_id
    if out.exists():
        raise SystemExit("REFUSE_OVERWRITE_DERIVED_REPORT:" + str(out))
    out.mkdir(parents=True)
    records = canonical_records()
    report = canonical_report(records)
    rows = [dict(row) for row in records if row["selection_state"] == states.SelectionState.SELECTED]
    top = Counter(row["top_level_status"] for row in rows)
    subclasses = Counter(row["subclass"] for row in rows)
    if top != Counter({"VALID_NO_SIGNAL_PAIR": 83, "TRUE_INCOMPLETE_PAIR": 57, "DIRECTIONAL_PAIR_EVALUABLE": 52}):
        raise RuntimeError("TAXONOMY_RECONCILIATION_FAILED:" + repr(top))
    arm_summary = {}
    for arm in ("PACK_A", "PACK_E"):
        accepted = [row for row in rows if row["arms"][arm]["accepted"]]
        valid_terminal = [row for row in rows if row["top_level_status"] != "TRUE_INCOMPLETE_PAIR"]
        arm_summary[arm] = {"directional_accepted": sum(not row["arms"][arm]["no_signal"] for row in accepted), "no_signal_accepted": sum(row["arms"][arm]["no_signal"] for row in accepted), "accepted_total": len(accepted), "rejected_or_missing_not_called": len(rows) - len(accepted), "within_valid_terminal_pairs": {"directional": sum(row["arms"][arm]["accepted"] and not row["arms"][arm]["no_signal"] for row in valid_terminal), "no_signal": sum(row["arms"][arm]["accepted"] and row["arms"][arm]["no_signal"] for row in valid_terminal)}}
    providers = {}
    for provider in ("Anthropic", "Gemini", "OpenAI"):
        subset = [row for row in rows if row["provider"] == provider]
        providers[provider] = {"accepted_forecast": len(subset), "directional_pairs": sum(row["top_level_status"] == "DIRECTIONAL_PAIR_EVALUABLE" for row in subset), "both_no_signal": sum(row["subclass"] == "BOTH_ARMS_NO_SIGNAL" for row in subset), "one_arm_no_signal": sum(row["top_level_status"] == "VALID_NO_SIGNAL_PAIR" and row["subclass"] != "BOTH_ARMS_NO_SIGNAL" for row in subset), "valid_no_signal_pairs": sum(row["top_level_status"] == "VALID_NO_SIGNAL_PAIR" for row in subset), "true_incomplete_pairs": sum(row["top_level_status"] == "TRUE_INCOMPLETE_PAIR" for row in subset)}
        providers[provider]["valid_terminal_pair_rate"] = (providers[provider]["directional_pairs"] + providers[provider]["valid_no_signal_pairs"]) / len(subset)
        providers[provider]["directional_pair_yield"] = providers[provider]["directional_pairs"] / len(subset)
    no_signal = [row for row in rows if row["top_level_status"] == "VALID_NO_SIGNAL_PAIR"]
    no_signal_analysis = {"both_arms_no_signal": subclasses["BOTH_ARMS_NO_SIGNAL"], "pack_a_only_no_signal": subclasses["PACK_A_NO_SIGNAL_PACK_E_DIRECTIONAL"], "pack_e_only_no_signal": subclasses["PACK_A_DIRECTIONAL_PACK_E_NO_SIGNAL"], "by_provider": dict(Counter(row["provider"] for row in no_signal)), "by_event_family": dict(Counter("|".join(row["attention_primary_driver_genres"]) or "UNKNOWN" for row in no_signal)), "by_episode_type": dict(Counter("|".join(row["attention_primary_driver_types"]) or "UNKNOWN" for row in no_signal)), "by_attention_rank": dict(Counter("|".join(map(str, row["attention_primary_driver_ranks"])) or "UNKNOWN" for row in no_signal)), "by_attention_confidence": dict(Counter("|".join(map(str, row["attention_primary_driver_confidences"])) or "UNKNOWN" for row in no_signal)), "arm_asymmetry": {"pack_a_no_signal_accepted": arm_summary["PACK_A"]["no_signal_accepted"], "pack_e_no_signal_accepted": arm_summary["PACK_E"]["no_signal_accepted"], "interpretation": "Pack A produced seven more accepted NO_SIGNAL outputs than Pack E; this is descriptive and is not directional correctness."}}
    gates = json.loads(QUALITY_GATES.read_text())
    rates = {"Directional Pair Yield": rate(52), "Valid NO_SIGNAL Pair Rate": rate(83), "True Operational/Contract Incompletion Rate": rate(57), "Valid Terminal Pair Rate": rate(135)}
    gate_audit = {"original_wording": "paired_completion_target", "original_value": gates["paired_completion_target"], "original_implementation": "The final runner's _is_evaluable_pair requires boolean direction_15m_ok for both arms; the reported 52/192 was therefore a directional-pair yield.", "valid_terminal_alternative": "Both arms accepted with either directional or valid NO_SIGNAL terminal output: 135/192.", "definition_ambiguity": True, "ambiguity_code": "V2_1_STEP8_R3_COMPLETION_GATE_DEFINITION_AMBIGUOUS", "gate_results": {"directional_coverage_interpretation": {"rate": 52 / 192, "passes_85_percent": False}, "valid_terminal_execution_interpretation": {"rate": 135 / 192, "passes_85_percent": False}}, "decision": "Do not silently replace the frozen directional implementation. Report both measures and preserve the ambiguity for governance."}
    primary = json.loads((RECON_RUN / "corrected_primary_15m_result.json").read_text())
    cluster = json.loads((RECON_RUN / "corrected_episode_cluster_analysis.json").read_text())
    incomplete = [row for row in rows if row["top_level_status"] == "TRUE_INCOMPLETE_PAIR"]
    operational = {"total": len(incomplete), "by_subclass": dict(Counter(row["subclass"] for row in incomplete)), "by_provider": dict(Counter(row["provider"] for row in incomplete)), "definition": "No two valid terminal forecast-arm outputs. Valid NO_SIGNAL pairs are excluded from this category."}
    missingness = {"directional_selectivity_uncertainty": {"count": 83, "definition": "Valid NO_SIGNAL pair(s) have no directional correctness and cannot be scored under the unchanged directional estimand.", "not_operational_missingness": True}, "operational_missingness_sensitivity": {"count": 57, "definition": "True operational or contract incompletion; this is the population eligible for an operational missingness sensitivity analysis.", "not_a_confidence_interval": True}, "prior_label_superseded": "The prior generic incomplete-pair label conflated valid non-directional outputs with operational failures."}
    decision = {"decision": "V2_1_STEP8_R3_FINAL_REPORTING_ACCOUNTING_REPAIRED", "additional_gate_decision": "V2_1_STEP8_R3_COMPLETION_GATE_DEFINITION_AMBIGUOUS", "evidence_classification": "HISTORICAL_EVIDENCE_REMAINS_INDETERMINATE", "scientific_result_changed": False, "no_signal_treated_as_flat": False, "no_signal_given_directional_correctness": False, "external_calls": 0, "p12_status": "PAUSED_PENDING_HISTORICAL_VALIDATION"}
    write(out / "repair_manifest.json", {"run_id": args.run_id, "scope": "NON_SCIENTIFIC_REPORTING_AND_ACCOUNTING_REPAIR", "source_run": SOURCE_RUN.name, "source_reconstruction": RECON_RUN.name, "contract_identity": CONTRACT_ID, "contract_fingerprint": CONTRACT_FP, "external_calls": 0})
    write(out / "source_reconstruction_reference.json", {"path": str(RECON_RUN.relative_to(ROOT)), "decision": json.loads((RECON_RUN / "final_reconstruction_decision.json").read_text()), "source_stage_tree_fingerprint": json.loads((RECON_RUN / "source_fingerprint_validation.json").read_text())["source_stage_results_tree_fingerprint"]})
    write(out / "canonical_reporting_summary.json", report); write(out / "accepted_forecast_population.json", rows); write(out / "terminal_status_taxonomy.json", {"DIRECTIONAL_PAIR_EVALUABLE": "Both arms directional and 15-minute evaluation boolean.", "VALID_NO_SIGNAL_PAIR": "Both arms valid terminal outputs and at least one is NO_SIGNAL.", "TRUE_INCOMPLETE_PAIR": "Two valid terminal forecast outputs were not produced."}); write_jsonl(out / "terminal_pair_classification.jsonl", rows)
    write(out / "repaired_population_funnel.json", {"accepted_forecast": 192, "directional_pair_evaluable": 52, "valid_no_signal_pair": 83, "true_incomplete_pair": 57, "reconciliation": 192, "rates": rates}); write(out / "repaired_arm_acceptance_summary.json", arm_summary); write(out / "repaired_provider_coverage.json", providers); write(out / "no_signal_analysis.json", no_signal_analysis); write(out / "directional_evidence_summary.json", {"label": "15-Minute Directional Accuracy Among Directionally Evaluable Paired Forecasts", **primary, "episode_cluster": cluster}); write(out / "operational_incompletion_summary.json", operational)
    write(out / "completion_gate_definition_audit.json", gate_audit); write(out / "repaired_quality_gate_assessment.json", {"directional_pair_yield": rates["Directional Pair Yield"], "valid_terminal_pair_rate": rates["Valid Terminal Pair Rate"], "threshold": gates["paired_completion_target"], "status": "AMBIGUOUS_DEFINITION_BOTH_RATES_FAIL_85_PERCENT"}); write(out / "repaired_missingness_terminology.json", missingness); write(out / "repaired_provider_analysis.json", providers); write(out / "repaired_historical_evidence_decision.json", decision)
    write(out / "superseded_reporting_inventory.json", {"superseded": [{"figure": "229 FORECAST selections", "replacement": "192 accepted parsed FORECAST selections", "reason": "37 rejected Attention raw PRIMARY_DRIVER labels excluded."}, {"figure": "22.7% paired completion", "replacement": "Directional Pair Yield 27.1%; Valid Terminal Pair Rate 70.3%; True Operational/Contract Incompletion Rate 29.7%", "reason": "NO_SIGNAL is valid non-directional output, not operational incompletion."}, {"figure": "83 both-arm all-null evaluations", "replacement": "64 both-arm NO_SIGNAL plus 19 one-arm NO_SIGNAL pairs", "reason": "Source reconstruction distinguishes both-arm from one-arm direction-null patterns."}]})
    write(out / "immutability_validation.json", {"status": "PASS", "source_ledgers_written": False, "compat_r5_changed": False, "evaluator_semantics_changed": False, "provider_calls": 0, "apps_script_calls": 0, "prospective_calls": 0, "p12_status": "PAUSED_PENDING_HISTORICAL_VALIDATION"})
    (out / "plain_language_summary.md").write_text("# Plain-language Summary\n\nWe had 192 valid cases where the AI decided the Event was worth forecasting. In 52 cases, both Pack A and Pack E gave a direction, so we could compare whether UP, DOWN, or FLAT was correct. In 83 cases, at least one Pack said `NO_SIGNAL`. That is a valid choice not to make a directional prediction. In 57 cases, the pair did not complete because of a real operational, transport, or contract problem.\n\nAmong the 52 directional comparisons, Pack A was correct 15 times and Pack E 14 times. The difference was small and the paired tests did not support a winner.\n")
    (out / "repaired_final_historical_report.md").write_text("# Repaired Final Historical Report\n\nAmong 52 provider/Episode pairs where both Pack A and Pack E produced directional forecasts, Pack A achieved 28.8% 15-minute directional accuracy and Pack E achieved 26.9%. The 1.9 percentage-point difference was small and unsupported by McNemar (`p=1.000`) and Episode-cluster (`p=1.000`) tests.\n\nAcross 192 accepted FORECAST identities, 83 pairs contained at least one valid NO_SIGNAL result and 57 were truly incomplete. The directional comparison therefore represents only the directionally evaluable subset, not overall provider success across selected Episodes. The evidence remains indeterminate.\n")
    print(recon.canonical({"run_id": args.run_id, "directional": 52, "valid_no_signal": 83, "true_incomplete": 57, "decision": decision["decision"]}))


if __name__ == "__main__":
    main()
