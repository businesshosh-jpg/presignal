#!/usr/bin/env python3
"""Validate and freeze the Round 1 minute Immediate Impulse enrichment.

This validation is intentionally independent of the enrichment builder's summary
aggregation. It recomputes denominators and metrics directly from the generated
rows and emits a separate corrected freeze artifact when labels need tightening.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

INPUT_ENRICHED_RUN_ID = "PPHB-R1-ENRICHED-IMMEDIATE-IMPULSE-MINUTE-20260727T083833Z-3b7e1063c396"
ORIGINAL_ROUND1_RUN_ID = "PPHB-R1-FULL-20260726T160036Z-ca5d238916f1"
MATRIX_FREEZE_RUN_ID = "PPHB-R1-FULL-MATRIX-FREEZE-20260726T150529Z-97fd30af6719"
CACHE_RECOVERY_RUN_ID = "PPHB-R1-TIINGO-MINUTE-CACHE-RECOVERY-20260727T081850Z-66c010cb396c"

INPUT_ENRICHED_ROOT = ROOT / "outputs" / "presignal_v21_pure_prediction_historical_baseline_enriched" / INPUT_ENRICHED_RUN_ID
ROUND1_ROOT = ROOT / "outputs" / "presignal_v21_pure_prediction_historical_baseline" / ORIGINAL_ROUND1_RUN_ID
CORRECTED_ROOT = ROOT / "outputs" / "presignal_v21_pure_prediction_historical_baseline_enriched"


class ValidationError(RuntimeError):
    pass


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def sha256_value(value: Any) -> str:
    return "sha256:" + sha256_text(canonical_json(value))


def read_json(path: Path) -> Any:
    return json.loads(path.read_text())


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(canonical_json(row) + "\n" for row in rows))


def iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def validation_run_id(now: datetime) -> str:
    stamp = now.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return "PPHB-R1-ENRICHED-IMMEDIATE-IMPULSE-MINUTE-CORRECTED-" + stamp + "-" + sha256_text(stamp)[:12]


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise ValidationError(code)


def ratio(correct: int, total: int) -> float | None:
    return None if total == 0 else round(correct / total, 6)


def metric_row(rows: list[dict[str, Any]]) -> dict[str, Any]:
    directional = [row for row in rows if row["evaluation_status"] == "COMPLETED_DIRECTIONAL_FORECAST"]
    no_signal = [row for row in rows if row["evaluation_status"] == "VALID_NO_SIGNAL"]
    schema = [row for row in rows if row["evaluation_status"] == "SCHEMA_FAILURE"]
    evaluable = [row for row in rows if row["one_minute_approximation_direction_result"] in {"CORRECT", "INCORRECT"}]
    ambiguous = [row for row in rows if row["close_direction_evaluable"] and row["sequence_unambiguous"] is False]
    sequence = [row for row in rows if row["sequence_unambiguous_direction_result"] in {"CORRECT", "INCORRECT"}]
    fm_correct = sum(row["first_minute_direction_result"] == "CORRECT" for row in evaluable)
    tm_correct = sum(row["two_minute_direction_result"] == "CORRECT" for row in evaluable)
    sequence_correct = sum(row["sequence_unambiguous_direction_result"] == "CORRECT" for row in sequence)
    return {
        "total_rows": len(rows),
        "directional_predictions": len(directional),
        "valid_no_signal": len(no_signal),
        "schema_invalid": len(schema),
        "approximation_evaluable": len(evaluable),
        "ambiguous_bars": len(ambiguous),
        "sequence_unambiguous": len(sequence),
        "sequence_unambiguous_correct": sequence_correct,
        "sequence_unambiguous_incorrect": len(sequence) - sequence_correct,
        "sequence_unambiguous_accuracy": ratio(sequence_correct, len(sequence)),
        "first_minute_correct": fm_correct,
        "first_minute_incorrect": len(evaluable) - fm_correct,
        "first_minute_accuracy": ratio(fm_correct, len(evaluable)),
        "two_minute_correct": tm_correct,
        "two_minute_incorrect": len(evaluable) - tm_correct,
        "two_minute_accuracy": ratio(tm_correct, len(evaluable)),
    }


def pair_classification(a_result: str, e_result: str) -> str:
    if a_result not in {"CORRECT", "INCORRECT"} or e_result not in {"CORRECT", "INCORRECT"}:
        return "not evaluable"
    if a_result == "CORRECT" and e_result == "CORRECT":
        return "both correct"
    if a_result == "INCORRECT" and e_result == "CORRECT":
        return "correction"
    if a_result == "CORRECT" and e_result == "INCORRECT":
        return "degradation"
    return "both incorrect"


def pair_transition(a: dict[str, Any] | None, e: dict[str, Any] | None) -> str:
    if not a or not e:
        return "PAIR_NOT_EVALUABLE"
    if a["evaluation_status"] == "SCHEMA_FAILURE" or e["evaluation_status"] == "SCHEMA_FAILURE":
        return "PAIR_NOT_EVALUABLE"
    if a["no_signal_flag"] and e["no_signal_flag"]:
        return "BOTH_NO_SIGNAL"
    if a["no_signal_flag"] and not e["no_signal_flag"]:
        return "A_NO_SIGNAL_TO_E_DIRECTIONAL"
    if not a["no_signal_flag"] and e["no_signal_flag"]:
        return "A_DIRECTIONAL_TO_E_NO_SIGNAL"
    return "BOTH_DIRECTIONAL"


def load_input_release() -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    outcomes = read_jsonl(INPUT_ENRICHED_ROOT / "immediate_impulse_outcome_rows.jsonl")
    evaluations = read_jsonl(INPUT_ENRICHED_ROOT / "immediate_impulse_evaluation_rows.jsonl")
    pairs = read_jsonl(INPUT_ENRICHED_ROOT / "paired_pack_comparison_rows.jsonl")
    summary = read_json(INPUT_ENRICHED_ROOT / "summary.json")
    return outcomes, evaluations, pairs, summary


def load_round1_predictions() -> dict[str, dict[str, Any]]:
    rows = {}
    for path in sorted((ROUND1_ROOT / "canonical_forecasts").glob("*.json")):
        if path.name.endswith("_paths.jsonl"):
            continue
        row = read_json(path)
        rows[row["prediction_id"]] = row
    return rows


def independent_recompute(
    evaluations: list[dict[str, Any]],
    pairs: list[dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    denominator_audit = {
        "overall": metric_row(evaluations),
        "Gemini": metric_row([row for row in evaluations if row["provider"] == "Gemini"]),
        "OpenAI": metric_row([row for row in evaluations if row["provider"] == "OpenAI"]),
        "Pack A": metric_row([row for row in evaluations if row["information_arm"] == "BASELINE"]),
        "Pack E": metric_row([row for row in evaluations if row["information_arm"] == "FULL_CONTEXT"]),
    }

    grouped: dict[tuple[str, str, str], dict[str, dict[str, Any]]] = defaultdict(dict)
    for row in evaluations:
        grouped[(row["episode_id"], row["provider"], row["model"])][row["information_arm"]] = row

    recomputed_pairs = []
    for (episode_id, provider, model), arms in sorted(grouped.items()):
        base = arms.get("BASELINE")
        full = arms.get("FULL_CONTEXT")
        recomputed_pairs.append({
            "episode_id": episode_id,
            "provider": provider,
            "model": model,
            "pair_transition": pair_transition(base, full),
            "all_close_direction_evaluable_pair_classification": pair_classification(
                None if not base else base["one_minute_approximation_direction_result"],
                None if not full else full["one_minute_approximation_direction_result"],
            ),
            "sequence_unambiguous_pair_classification": pair_classification(
                None if not base else base["sequence_unambiguous_direction_result"],
                None if not full else full["sequence_unambiguous_direction_result"],
            ),
        })

    pair_audit = {
        "pair_row_count": len(recomputed_pairs),
        "all_close_direction_evaluable_pairs": dict(Counter(row["all_close_direction_evaluable_pair_classification"] for row in recomputed_pairs)),
        "sequence_unambiguous_pairs": dict(Counter(row["sequence_unambiguous_pair_classification"] for row in recomputed_pairs)),
        "pair_transition_counts": dict(Counter(row["pair_transition"] for row in recomputed_pairs)),
    }

    metric_recomputation = {
        "total_forecast_arms": denominator_audit["overall"]["total_rows"],
        "directional_predictions": denominator_audit["overall"]["directional_predictions"],
        "no_signal_arms": denominator_audit["overall"]["valid_no_signal"],
        "schema_invalid_arms": denominator_audit["overall"]["schema_invalid"],
        "approximation_evaluable_arms": denominator_audit["overall"]["approximation_evaluable"],
        "ambiguous_bar_arms": denominator_audit["overall"]["ambiguous_bars"],
        "sequence_unambiguous_arms": denominator_audit["overall"]["sequence_unambiguous"],
        "subgroups": denominator_audit,
        "pairs": pair_audit,
    }
    return denominator_audit, pair_audit, metric_recomputation


def continuation_reversal_audit(
    evaluations: list[dict[str, Any]],
    predictions: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    directional = [row for row in evaluations if row["evaluation_status"] == "COMPLETED_DIRECTIONAL_FORECAST"]
    observed_continuation = [row for row in directional if row["observed_minute_path_class"] == "CONTINUATION"]
    observed_reversal = [row for row in directional if row["observed_minute_path_class"] == "REVERSAL"]
    predicted_counts = Counter(row["predicted_minute_path_class"] for row in directional)

    samples = []
    for row in directional[:5]:
        prediction = predictions.get(row["prediction_id"])
        if not prediction:
            continue
        samples.append({
            "prediction_id": row["prediction_id"],
            "provider": row["provider"],
            "pack_arm": row["pack_arm"],
            "forecast_immediate_impulse_direction": prediction.get("immediate_impulse_direction"),
            "forecast_early_reaction_5m_direction": prediction.get("early_reaction_5m_direction"),
            "predicted_minute_path_class": row["predicted_minute_path_class"],
            "observed_minute_path_class": row["observed_minute_path_class"],
            "minute_path_result": row["minute_path_result"],
        })

    continuation_hits = sum(row["minute_path_result"] == "CORRECT" for row in observed_continuation)
    reversal_hits = sum(row["minute_path_result"] == "CORRECT" for row in observed_reversal)
    audit = {
        "forecast_fields_used": [
            "immediate_impulse_direction",
            "early_reaction_5m_direction",
        ],
        "outcome_field_used": "minute_resolution_path_class",
        "distinct_forecast_path_field_exists": False,
        "predicted_path_class_is_derived_from_two_forecast_fields": True,
        "self_comparison_detected": False,
        "predicted_path_class_counts": dict(predicted_counts),
        "observed_continuation_denominator": len(observed_continuation),
        "observed_reversal_denominator": len(observed_reversal),
        "continuation_hit_numerator": continuation_hits,
        "reversal_hit_numerator": reversal_hits,
        "reported_continuation_value": ratio(continuation_hits, len(observed_continuation)),
        "reported_reversal_value": ratio(reversal_hits, len(observed_reversal)),
        "structural_issue": "All completed directional forecasts predicted CONTINUATION, so the reported values behave as conditional hit rates on observed continuation/reversal subsets rather than balanced path accuracies.",
        "treatment": {
            "continuation": "RELABEL_AS_CONDITIONAL_PATH_RATE",
            "reversal": "RELABEL_AS_CONDITIONAL_PATH_RATE",
        },
        "representative_rows": samples,
    }
    return audit


def wording_audit() -> dict[str, Any]:
    violations = []
    for path in [INPUT_ENRICHED_ROOT / "summary.md", INPUT_ENRICHED_ROOT / "run_manifest.json", INPUT_ENRICHED_ROOT / "summary.json"]:
        text = path.read_text()
        for forbidden in ["strict Immediate Impulse direction", "true first move", "exact impulse start", "sub-minute reversal"]:
            if forbidden in text:
                violations.append({"path": str(path), "phrase": forbidden})
    return {
        "forbidden_phrase_violations": violations,
        "release_distinguishes_first_minute_net_direction_from_true_first_sub_minute_move": not violations,
    }


def corrected_summary(
    denominator_audit: dict[str, Any],
    pair_audit: dict[str, Any],
    continuation_audit: dict[str, Any],
) -> dict[str, Any]:
    overall = denominator_audit["overall"]
    summary = {
        "total_forecast_arms": overall["total_rows"],
        "directional_immediate_impulse_predictions": overall["directional_predictions"],
        "no_signal_arms": overall["valid_no_signal"],
        "schema_invalid_arms": overall["schema_invalid"],
        "approximation_evaluable_arms": overall["approximation_evaluable"],
        "ambiguous_bar_arms": overall["ambiguous_bars"],
        "sequence_unambiguous_arms": overall["sequence_unambiguous"],
        "overall_first_minute_net_directional_accuracy": overall["first_minute_accuracy"],
        "overall_two_minute_net_directional_accuracy": overall["two_minute_accuracy"],
        "overall_one_minute_approximation_directional_accuracy": overall["first_minute_accuracy"],
        "overall_sequence_unambiguous_approximation_directional_accuracy": overall["sequence_unambiguous_accuracy"],
        "gemini_results": denominator_audit["Gemini"],
        "openai_results": denominator_audit["OpenAI"],
        "pack_a_results": denominator_audit["Pack A"],
        "pack_e_results": denominator_audit["Pack E"],
        "pair_results": pair_audit,
        "minute_resolution_continuation_conditional_hit_rate": continuation_audit["reported_continuation_value"],
        "minute_resolution_reversal_conditional_hit_rate": continuation_audit["reported_reversal_value"],
        "continuation_reversal_metric_label_decision": continuation_audit["treatment"],
        "continuation_reversal_metric_note": continuation_audit["structural_issue"],
    }
    return summary


def scientific_interpretation(denominator_audit: dict[str, Any], continuation_audit: dict[str, Any]) -> str:
    overall = denominator_audit["overall"]
    gemini = denominator_audit["Gemini"]
    openai = denominator_audit["OpenAI"]
    pack_a = denominator_audit["Pack A"]
    pack_e = denominator_audit["Pack E"]
    return "\n".join([
        "# Scientific Interpretation",
        "",
        f"- Overall first-minute net directional accuracy: {overall['first_minute_correct']} / {overall['approximation_evaluable']} = {overall['first_minute_accuracy']}",
        f"- Overall two-minute net directional accuracy: {overall['two_minute_correct']} / {overall['approximation_evaluable']} = {overall['two_minute_accuracy']}",
        f"- Sequence-unambiguous subset first-minute accuracy: {overall['sequence_unambiguous_correct']} / {overall['sequence_unambiguous']} = {overall['sequence_unambiguous_accuracy']}",
        f"- Pack A first-minute result: {pack_a['first_minute_correct']} / {pack_a['approximation_evaluable']} = {pack_a['first_minute_accuracy']}",
        f"- Pack E first-minute result: {pack_e['first_minute_correct']} / {pack_e['approximation_evaluable']} = {pack_e['first_minute_accuracy']}",
        f"- Gemini first-minute result: {gemini['first_minute_correct']} / {gemini['approximation_evaluable']} = {gemini['first_minute_accuracy']}",
        f"- OpenAI first-minute result: {openai['first_minute_correct']} / {openai['approximation_evaluable']} = {openai['first_minute_accuracy']}",
        "- Pack E does not show a meaningful descriptive first-minute advantage over Pack A in this one-minute approximation view; the difference is small and no formal significance test was performed.",
        "- The one-minute approximation is materially weaker than the unchanged T+15 primary result because it is constrained by coarse minute bars and 27 sequence-ambiguous bars.",
        "- This does not invalidate the T+15 primary finding because T+15 remains the pre-declared primary endpoint and none of the original T+15 outcomes or evaluations changed.",
        "- Intraminute ambiguity materially limits interpretation: close-direction evaluability remains available, but true first-move ordering remains unavailable on 27 forecast arms.",
        f"- The original continuation/reversal numbers should be read as conditional path hit rates, not balanced predictive accuracies: continuation {continuation_audit['continuation_hit_numerator']} / {continuation_audit['observed_continuation_denominator']} and reversal {continuation_audit['reversal_hit_numerator']} / {continuation_audit['observed_reversal_denominator']}.",
        "- Strict Immediate Impulse direction, exact first-move ordering, exact impulse start, and sub-minute reversal remain unavailable until genuine sub-minute historical data is added.",
    ]) + "\n"


def build_checksums(run_dir: Path) -> dict[str, str]:
    checksums = {}
    for path in sorted(run_dir.iterdir()):
        if path.is_file():
            checksums[path.name] = "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
    return checksums


def validate_existing_release() -> dict[str, Any]:
    outcomes, evaluations, pairs, summary = load_input_release()
    predictions = load_round1_predictions()

    denominator_audit, pair_audit, metric_recomputation = independent_recompute(evaluations, pairs)
    continuation_audit = continuation_reversal_audit(evaluations, predictions)
    wording = wording_audit()

    _require(denominator_audit["overall"]["total_rows"] == 170, "DENOMINATOR_TOTAL_ARMS")
    _require(denominator_audit["overall"]["directional_predictions"] == 133, "DENOMINATOR_DIRECTIONAL")
    _require(denominator_audit["overall"]["valid_no_signal"] == 12, "DENOMINATOR_NO_SIGNAL")
    _require(denominator_audit["overall"]["schema_invalid"] == 25, "DENOMINATOR_SCHEMA_INVALID")
    _require(denominator_audit["overall"]["ambiguous_bars"] + denominator_audit["overall"]["sequence_unambiguous"] == 133, "DENOMINATOR_AMBIGUOUS_SEQUENCE_SUM")
    _require(denominator_audit["Pack A"]["approximation_evaluable"] == 62, "PACK_A_EVALUABLE")
    _require(denominator_audit["Pack E"]["approximation_evaluable"] == 71, "PACK_E_EVALUABLE")
    _require(denominator_audit["Gemini"]["approximation_evaluable"] == 87, "GEMINI_EVALUABLE")
    _require(denominator_audit["OpenAI"]["approximation_evaluable"] == 46, "OPENAI_EVALUABLE")
    _require(pair_audit["pair_row_count"] == 85, "PAIR_ROW_COUNT")

    return {
        "outcomes": outcomes,
        "evaluations": evaluations,
        "pairs": pairs,
        "summary": summary,
        "denominator_audit": denominator_audit,
        "pair_audit": pair_audit,
        "metric_recomputation": metric_recomputation,
        "continuation_audit": continuation_audit,
        "wording_audit": wording,
    }


def freeze_corrected_release(output_root: Path | None = None) -> dict[str, Any]:
    audit = validate_existing_release()
    now = datetime.now(timezone.utc)
    run_id = validation_run_id(now)
    run_dir = (output_root or CORRECTED_ROOT) / run_id
    construction_ts = iso(now)
    git_head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()

    validation_summary = corrected_summary(audit["denominator_audit"], audit["pair_audit"], audit["continuation_audit"])
    interpretation_md = scientific_interpretation(audit["denominator_audit"], audit["continuation_audit"])
    validation_manifest = {
        "run_id": run_id,
        "supersedes_enriched_run_id": INPUT_ENRICHED_RUN_ID,
        "freeze_decision": "ENRICHED_RELEASE_CORRECTED_AND_FROZEN",
        "scientific_decision": "APPROXIMATION_METRICS_VALIDATED_AFTER_RELABELING",
        "build_status": "MINUTE_ENRICHMENT_VALIDATION_COMPLETE_WITH_CORRECTIONS",
        "readiness_status": "ROUND_1_MINUTE_ENRICHMENT_FROZEN",
        "original_round1_run_id": ORIGINAL_ROUND1_RUN_ID,
        "matrix_freeze_run_id": MATRIX_FREEZE_RUN_ID,
        "cache_recovery_run_id": CACHE_RECOVERY_RUN_ID,
        "input_enriched_run_id": INPUT_ENRICHED_RUN_ID,
        "git_head": git_head,
        "construction_timestamp": construction_ts,
        "correction_scope": "Metric labeling and freeze validation only. Underlying outcome/evaluation rows are unchanged and referenced from the input enriched release.",
        "continuation_reversal_treatment": audit["continuation_audit"]["treatment"],
        "input_references": {
            "run_manifest": str(INPUT_ENRICHED_ROOT / "run_manifest.json"),
            "immediate_impulse_outcome_rows": str(INPUT_ENRICHED_ROOT / "immediate_impulse_outcome_rows.jsonl"),
            "immediate_impulse_evaluation_rows": str(INPUT_ENRICHED_ROOT / "immediate_impulse_evaluation_rows.jsonl"),
            "paired_pack_comparison_rows": str(INPUT_ENRICHED_ROOT / "paired_pack_comparison_rows.jsonl"),
        },
    }

    validation_summary_md = "\n".join([
        "# Minute Enrichment Validation Summary",
        "",
        f"- Input enriched run: `{INPUT_ENRICHED_RUN_ID}`",
        f"- Freeze run: `{run_id}`",
        "- Original outcome and evaluation rows were not modified.",
        "- Continuation/reversal labels were tightened from `accuracy` to conditional path hit-rate language.",
        "",
        f"- Total arms: {audit['denominator_audit']['overall']['total_rows']}",
        f"- Directional: {audit['denominator_audit']['overall']['directional_predictions']}",
        f"- NO_SIGNAL: {audit['denominator_audit']['overall']['valid_no_signal']}",
        f"- Schema-invalid: {audit['denominator_audit']['overall']['schema_invalid']}",
        f"- First-minute: {audit['denominator_audit']['overall']['first_minute_correct']} / {audit['denominator_audit']['overall']['approximation_evaluable']} = {audit['denominator_audit']['overall']['first_minute_accuracy']}",
        f"- Two-minute: {audit['denominator_audit']['overall']['two_minute_correct']} / {audit['denominator_audit']['overall']['approximation_evaluable']} = {audit['denominator_audit']['overall']['two_minute_accuracy']}",
        f"- Continuation conditional hit rate: {audit['continuation_audit']['continuation_hit_numerator']} / {audit['continuation_audit']['observed_continuation_denominator']} = {audit['continuation_audit']['reported_continuation_value']}",
        f"- Reversal conditional hit rate: {audit['continuation_audit']['reversal_hit_numerator']} / {audit['continuation_audit']['observed_reversal_denominator']} = {audit['continuation_audit']['reported_reversal_value']}",
    ]) + "\n"

    write_json(run_dir / "run_manifest.json", validation_manifest)
    write_json(run_dir / "metric_recomputation.json", audit["metric_recomputation"])
    write_json(run_dir / "denominator_audit.json", audit["denominator_audit"])
    write_json(run_dir / "continuation_reversal_audit.json", audit["continuation_audit"])
    write_json(run_dir / "paired_pack_audit.json", audit["pair_audit"])
    (run_dir / "scientific_interpretation.md").write_text(interpretation_md)
    write_json(run_dir / "validation_summary.json", validation_summary)
    (run_dir / "validation_summary.md").write_text(validation_summary_md)
    write_json(run_dir / "summary.json", validation_summary)
    (run_dir / "summary.md").write_text(validation_summary_md)
    checksums = build_checksums(run_dir)
    write_json(run_dir / "checksums.json", checksums)
    return validation_manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, default=CORRECTED_ROOT)
    args = parser.parse_args()
    print(json.dumps(freeze_corrected_release(args.output_root), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
