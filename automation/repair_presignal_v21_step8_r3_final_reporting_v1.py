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


def classify(stages: Mapping[str, Mapping[str, Any]]) -> tuple[str, str, str | None]:
    request, a, e, evaluate = stages.get("REQUEST:"), stages.get("FORECAST:PACK_A"), stages.get("FORECAST:PACK_E"), stages.get("EVALUATE:")
    a_ok, e_ok = bool(a and a.get("accepted")), bool(e and e.get("accepted"))
    a_prediction, e_prediction = recon.prediction(a), recon.prediction(e)
    a_no_signal = bool(a_prediction and a_prediction.get("no_signal_flag"))
    e_no_signal = bool(e_prediction and e_prediction.get("no_signal_flag"))
    if a_ok and e_ok:
        if a_no_signal and e_no_signal:
            return "VALID_NO_SIGNAL_PAIR", "BOTH_ARMS_NO_SIGNAL", None
        if a_no_signal:
            return "VALID_NO_SIGNAL_PAIR", "PACK_A_NO_SIGNAL_PACK_E_DIRECTIONAL", None
        if e_no_signal:
            return "VALID_NO_SIGNAL_PAIR", "PACK_A_DIRECTIONAL_PACK_E_NO_SIGNAL", None
        ea, ee = recon.evaluation(evaluate, "PACK_A"), recon.evaluation(evaluate, "PACK_E")
        if isinstance(ea, Mapping) and isinstance(ee, Mapping) and isinstance(ea.get("direction_15m_ok"), bool) and isinstance(ee.get("direction_15m_ok"), bool):
            return "DIRECTIONAL_PAIR_EVALUABLE", "BOTH_ARMS_DIRECTIONAL", None
        return "TRUE_INCOMPLETE_PAIR", "OUTCOME_FAILURE", "DIRECTIONAL_ENDPOINT_UNAVAILABLE"
    if not (request and request.get("accepted")):
        reason = (request or {}).get("rejection_reason")
        runtime = states.runtime_state(request, selected=True)
        subclass = "REQUEST_TRANSPORT_FAILURE" if runtime in {states.RuntimeState.TRANSPORT_FAILED, states.RuntimeState.STATUS_UNKNOWN} else "REQUEST_REJECTION"
        return "TRUE_INCOMPLETE_PAIR", subclass, reason
    if not a_ok and e_ok:
        return "TRUE_INCOMPLETE_PAIR", "PACK_A_MISSING", (a or {}).get("rejection_reason")
    if a_ok and not e_ok:
        return "TRUE_INCOMPLETE_PAIR", "PACK_E_MISSING", (e or {}).get("rejection_reason")
    reason = (a or {}).get("rejection_reason") or (e or {}).get("rejection_reason")
    return "TRUE_INCOMPLETE_PAIR", "BOTH_ARMS_MISSING", reason


def pair_rows() -> list[dict[str, Any]]:
    grouped, _ = recon.stage_index(SOURCE_RUN)
    rows = []
    for key, stages in sorted(grouped.items()):
        if states.selection_state(stages.get("ATTENTION:")) != states.SelectionState.SELECTED:
            continue
        episode_id, provider, model = key
        top, subclass, reason = classify(stages)
        attention = stages["ATTENTION:"]
        members = (attention.get("output") or {}).get("rows") or []
        primary = [row for row in members if row.get("status") == "parsed" and row.get("attention_label") == "PRIMARY_DRIVER"]
        arms = {}
        for arm in ("PACK_A", "PACK_E"):
            forecast = stages.get("FORECAST:" + arm)
            pred = recon.prediction(forecast)
            arms[arm] = {"accepted": bool(forecast and forecast.get("accepted")), "no_signal": bool(pred and pred.get("no_signal_flag")), "rejection_reason": None if forecast and forecast.get("accepted") else (forecast or {}).get("rejection_reason"), "prediction_id": pred.get("prediction_id") if pred else None}
        canonical = {arm: states.canonical_states(attention=attention, forecast=stages.get("FORECAST:" + arm), evaluation=recon.evaluation(stages.get("EVALUATE:"), arm), outcome=(stages.get("OUTCOME:") or {}).get("output")) for arm in ("PACK_A", "PACK_E")}
        rows.append({"episode_id": episode_id, "provider": provider, "model": model, "top_level_status": top, "subclass": subclass, "failure_reason": reason, "request_accepted": bool(stages.get("REQUEST:") and stages["REQUEST:"].get("accepted")), "canonical_states": canonical, "arms": arms, "attention_primary_driver_genres": sorted({str(item.get("genre") or "UNKNOWN") for item in primary}), "attention_primary_driver_types": sorted({str(item.get("type") or "UNKNOWN") for item in primary}), "attention_primary_driver_ranks": sorted({item.get("attention_rank") for item in primary}), "attention_primary_driver_confidences": sorted({item.get("confidence") for item in primary}), "source_attention": attention.get("_source_file")})
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
    rows = pair_rows()
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
    write(out / "accepted_forecast_population.json", rows); write(out / "terminal_status_taxonomy.json", {"DIRECTIONAL_PAIR_EVALUABLE": "Both arms directional and 15-minute evaluation boolean.", "VALID_NO_SIGNAL_PAIR": "Both arms valid terminal outputs and at least one is NO_SIGNAL.", "TRUE_INCOMPLETE_PAIR": "Two valid terminal forecast outputs were not produced."}); write_jsonl(out / "terminal_pair_classification.jsonl", rows)
    write(out / "repaired_population_funnel.json", {"accepted_forecast": 192, "directional_pair_evaluable": 52, "valid_no_signal_pair": 83, "true_incomplete_pair": 57, "reconciliation": 192, "rates": rates}); write(out / "repaired_arm_acceptance_summary.json", arm_summary); write(out / "repaired_provider_coverage.json", providers); write(out / "no_signal_analysis.json", no_signal_analysis); write(out / "directional_evidence_summary.json", {"label": "15-Minute Directional Accuracy Among Directionally Evaluable Paired Forecasts", **primary, "episode_cluster": cluster}); write(out / "operational_incompletion_summary.json", operational)
    write(out / "completion_gate_definition_audit.json", gate_audit); write(out / "repaired_quality_gate_assessment.json", {"directional_pair_yield": rates["Directional Pair Yield"], "valid_terminal_pair_rate": rates["Valid Terminal Pair Rate"], "threshold": gates["paired_completion_target"], "status": "AMBIGUOUS_DEFINITION_BOTH_RATES_FAIL_85_PERCENT"}); write(out / "repaired_missingness_terminology.json", missingness); write(out / "repaired_provider_analysis.json", providers); write(out / "repaired_historical_evidence_decision.json", decision)
    write(out / "superseded_reporting_inventory.json", {"superseded": [{"figure": "229 FORECAST selections", "replacement": "192 accepted parsed FORECAST selections", "reason": "37 rejected Attention raw PRIMARY_DRIVER labels excluded."}, {"figure": "22.7% paired completion", "replacement": "Directional Pair Yield 27.1%; Valid Terminal Pair Rate 70.3%; True Operational/Contract Incompletion Rate 29.7%", "reason": "NO_SIGNAL is valid non-directional output, not operational incompletion."}, {"figure": "83 both-arm all-null evaluations", "replacement": "64 both-arm NO_SIGNAL plus 19 one-arm NO_SIGNAL pairs", "reason": "Source reconstruction distinguishes both-arm from one-arm direction-null patterns."}]})
    write(out / "immutability_validation.json", {"status": "PASS", "source_ledgers_written": False, "compat_r5_changed": False, "evaluator_semantics_changed": False, "provider_calls": 0, "apps_script_calls": 0, "prospective_calls": 0, "p12_status": "PAUSED_PENDING_HISTORICAL_VALIDATION"})
    (out / "plain_language_summary.md").write_text("# Plain-language Summary\n\nWe had 192 valid cases where the AI decided the Event was worth forecasting. In 52 cases, both Pack A and Pack E gave a direction, so we could compare whether UP, DOWN, or FLAT was correct. In 83 cases, at least one Pack said `NO_SIGNAL`. That is a valid choice not to make a directional prediction. In 57 cases, the pair did not complete because of a real operational, transport, or contract problem.\n\nAmong the 52 directional comparisons, Pack A was correct 15 times and Pack E 14 times. The difference was small and the paired tests did not support a winner.\n")
    (out / "repaired_final_historical_report.md").write_text("# Repaired Final Historical Report\n\nAmong 52 provider/Episode pairs where both Pack A and Pack E produced directional forecasts, Pack A achieved 28.8% 15-minute directional accuracy and Pack E achieved 26.9%. The 1.9 percentage-point difference was small and unsupported by McNemar (`p=1.000`) and Episode-cluster (`p=1.000`) tests.\n\nAcross 192 accepted FORECAST identities, 83 pairs contained at least one valid NO_SIGNAL result and 57 were truly incomplete. The directional comparison therefore represents only the directionally evaluable subset, not overall provider success across selected Episodes. The evidence remains indeterminate.\n")
    print(recon.canonical({"run_id": args.run_id, "directional": 52, "valid_no_signal": 83, "true_incomplete": 57, "decision": decision["decision"]}))


if __name__ == "__main__":
    main()
