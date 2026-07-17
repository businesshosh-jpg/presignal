import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from automation.build_market_sessions_shadow_v0 import (
    DIAGNOSTICS_SPREADSHEET_ID,
    PROJECT_OVERVIEWS_SPREADSHEET_ID,
    REGISTRY_HEADERS,
    REGISTRY_SHEET,
    _column_letter,
    _ensure_sheet,
    _norm,
    _sheet_to_rows,
    _write_rows,
)
from automation.build_session_information_requests_v0 import _iso_now, _truncate_text
from automation.google_clients import batch_update_values, build_sheets_service, load_credentials


SCHEMA_VERSION = "presignal_v2_controlled_accuracy_evaluation_review_0.1"
REVIEW_VERSION = "controlled_accuracy_evaluation_review_v0"
PHASE_LABEL = "PreSignal v2.0 Phase 9A-5G"
REGISTRY_CATEGORY = "PRESIGNAL_V2_CONTROLLED_ACCURACY_EVALUATION_REVIEW"
REGISTRY_OWNER_MODULE = "market_state"

INPUT_9A5F = [
    "Controlled_Accuracy_Evaluation",
    "Controlled_Accuracy_Experiment_Results",
    "Controlled_Accuracy_Comparison_Results",
    "Controlled_Accuracy_Metric_Results",
    "Controlled_Accuracy_Invalid_Output_Results",
    "Controlled_Accuracy_Governance_Audit",
    "Controlled_Accuracy_Evaluation_Summary",
]

INPUT_9A5E = [
    "Accuracy_Execution_Approval",
    "Accuracy_Execution_Freeze_Record",
    "Accuracy_Execution_Governance_Review",
    "Accuracy_Execution_Risk_Assessment",
    "Accuracy_Execution_Interpretation_Guardrails",
    "Accuracy_Execution_Approval_Summary",
]

INPUT_9A5D = [
    "Controlled_Accuracy_Eval_Dry_Run",
    "Controlled_Accuracy_Eligible_Row_Preview",
    "Controlled_Accuracy_Outcome_Match_Preview",
    "Controlled_Accuracy_Comparison_Pair_Preview",
    "Controlled_Accuracy_Metric_Row_Preview",
    "Controlled_Accuracy_Invalid_Row_Audit",
    "Controlled_Accuracy_Execution_Governance_Audit",
    "Controlled_Accuracy_Execution_Dry_Run_Summary",
]

INPUT_DESIGN = [
    "Behavior_To_Accuracy_Testable_Hypotheses",
    "Behavior_To_Accuracy_Eligible_Hypotheses",
    "Behavior_To_Accuracy_Excluded_Hypotheses",
    "Behavior_To_Accuracy_Design_Summary",
    "Accuracy_Evaluation_Plan",
    "Accuracy_Evaluation_Experiment_Definition",
    "Accuracy_Evaluation_Metric_Execution_Plan",
    "Accuracy_Evaluation_Plan_Summary",
    "Controlled_Accuracy_Evaluation_Design",
    "Controlled_Accuracy_Experiment_Schema",
    "Controlled_Accuracy_Metric_Logic",
    "Controlled_Accuracy_Comparison_Logic",
    "Controlled_Accuracy_Design_Summary",
]

INPUT_BEHAVIOR = [
    "Pack_Behavior_Tier2_Generalization_Review",
    "Pack_Behavior_Tier2_Hypothesis_Generalization",
    "Pack_Behavior_Tier2_Provider_Generalization",
    "Pack_Behavior_Tier2_Transition_Generalization",
    "Pack_Behavior_Tier2_Field_Generalization",
    "Pack_Behavior_Tier2_NoSignal_Generalization",
    "Pack_Behavior_Tier2_Invalid_Output_Generalization",
    "Pack_Behavior_Tier2_Generalization_Summary",
]

OUTPUT_REVIEW = "Controlled_Accuracy_Evaluation_Review"
OUTPUT_HYPOTHESIS = "Accuracy_Hypothesis_Review"
OUTPUT_BEHAVIOR_VS_ACCURACY = "Behavior_vs_Accuracy_Review"
OUTPUT_PACK = "Pack_Comparison_Accuracy_Review"
OUTPUT_PROVIDER = "Provider_Accuracy_Review"
OUTPUT_METRIC = "Metric_Interpretation_Review"
OUTPUT_LIMITATION = "Accuracy_Limitation_Audit"
OUTPUT_GOVERNANCE = "Accuracy_Governance_Review"
OUTPUT_RECOMMENDATION = "Accuracy_Next_Phase_Recommendation"
OUTPUT_SUMMARY = "Controlled_Accuracy_Evaluation_Review_Summary"

REVIEW_HEADERS = [
    "generated_ts",
    "schema_version",
    "review_version",
    "review_run_id",
    "review_area",
    "review_status",
    "evidence_scope",
    "experiments_reviewed",
    "eligible_rows_evaluated",
    "comparison_pairs_evaluated",
    "metrics_reviewed",
    "direction_denominator",
    "direction_correct_count",
    "direction_match_rate",
    "overall_denominator",
    "overall_ok_count",
    "overall_ok_rate",
    "accuracy_signal_classification",
    "review_conclusion",
    "recommended_next_action",
    "production_excluded",
    "notes",
]

HYPOTHESIS_HEADERS = [
    "generated_ts",
    "schema_version",
    "review_version",
    "review_run_id",
    "accuracy_hypothesis_id",
    "source_behavior_hypothesis_id",
    "experiment_id",
    "experiment_result_direction_rate",
    "experiment_result_overall_rate",
    "primary_metric_result_summary",
    "secondary_metric_result_summary",
    "comparison_evidence_summary",
    "behavior_to_accuracy_transfer_status",
    "hypothesis_support_status",
    "sample_size_warning",
    "invalid_output_impact",
    "interpretation",
    "recommended_status",
    "recommended_next_action",
    "production_excluded",
    "notes",
]

BEHAVIOR_VS_ACCURACY_HEADERS = [
    "generated_ts",
    "schema_version",
    "review_version",
    "review_run_id",
    "behavior_hypothesis_id",
    "behavior_generalization_status",
    "accuracy_hypothesis_id",
    "behavior_evidence_summary",
    "accuracy_result_summary",
    "transfer_result",
    "behavior_accuracy_alignment",
    "interpretation",
    "next_research_action",
    "notes",
]

PACK_HEADERS = [
    "generated_ts",
    "schema_version",
    "review_version",
    "review_run_id",
    "comparison_id",
    "baseline_pack",
    "treatment_pack",
    "provider_scope",
    "pair_count",
    "direction_rate_baseline",
    "direction_rate_treatment",
    "direction_delta",
    "overall_rate_baseline",
    "overall_rate_treatment",
    "overall_delta",
    "signal_discipline_result",
    "interpretation",
    "sample_size_warning",
    "recommended_action",
    "production_excluded",
    "notes",
]

PROVIDER_HEADERS = [
    "generated_ts",
    "schema_version",
    "review_version",
    "review_run_id",
    "provider",
    "eligible_rows_evaluated",
    "invalid_outputs",
    "direction_denominator",
    "direction_correct_count",
    "direction_match_rate",
    "overall_denominator",
    "overall_ok_count",
    "overall_ok_rate",
    "behavior_profile_summary",
    "accuracy_profile_summary",
    "interpretation",
    "provider_ranking_forbidden",
    "production_routing_forbidden",
    "notes",
]

METRIC_HEADERS = [
    "generated_ts",
    "schema_version",
    "review_version",
    "review_run_id",
    "metric_id",
    "metric_name",
    "metric_value_or_summary",
    "denominator",
    "numerator",
    "experiment_id",
    "comparison_id",
    "metric_interpretation",
    "risk_of_overinterpretation",
    "next_use_recommendation",
    "notes",
]

LIMITATION_HEADERS = [
    "generated_ts",
    "schema_version",
    "review_version",
    "review_run_id",
    "limitation_id",
    "limitation_name",
    "description",
    "affected_hypotheses",
    "affected_experiments",
    "severity",
    "impact_on_interpretation",
    "recommended_mitigation",
    "blocks_next_phase",
    "notes",
]

GOVERNANCE_HEADERS = [
    "generated_ts",
    "schema_version",
    "review_version",
    "review_run_id",
    "check_id",
    "check_name",
    "expected_value",
    "actual_value",
    "status",
    "notes",
]

RECOMMENDATION_HEADERS = [
    "generated_ts",
    "schema_version",
    "review_version",
    "review_run_id",
    "recommendation_id",
    "recommendation_type",
    "recommendation",
    "rationale",
    "required_inputs",
    "blocked_by",
    "priority",
    "notes",
]

SUMMARY_HEADERS = [
    "generated_ts",
    "schema_version",
    "review_version",
    "review_run_id",
    "build_status",
    "final_interpretation",
    "experiments_reviewed",
    "hypotheses_reviewed",
    "hypotheses_supported",
    "hypotheses_partially_supported",
    "hypotheses_not_supported",
    "hypotheses_inconclusive",
    "hypotheses_retired",
    "direction_denominator",
    "direction_correct_count",
    "direction_match_rate",
    "overall_denominator",
    "overall_ok_count",
    "overall_ok_rate",
    "strongest_supported_hypothesis",
    "strongest_pack_comparison_signal",
    "strongest_provider_accuracy_profile",
    "highest_risk_limitation",
    "primary_interpretation",
    "provider_calls_performed",
    "forecast_generation_performed",
    "provider_rerun_count",
    "evaluation_rerun_count",
    "accuracy_results_modified",
    "production_behavior_change_count",
    "production_sheet_write_count",
    "ready_for_replication_design",
    "ready_for_hypothesis_revision",
    "ready_for_production",
    "recommended_next_step",
    "notes",
]


def _upper(value: Any) -> str:
    return _norm(value).upper()


def _bool(value: Any) -> bool:
    return _upper(value) in {"TRUE", "YES", "1", "Y"}


def _float(value: Any) -> Optional[float]:
    raw = _norm(value)
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def _int(value: Any) -> int:
    val = _float(value)
    return int(val) if val is not None else 0


def _fmt(value: Optional[float]) -> str:
    if value is None:
        return ""
    return f"{value:.6f}"


def _run_id(generated_ts: str) -> str:
    compact = generated_ts.replace("-", "").replace(":", "").replace("Z", "Z")
    return f"controlled_accuracy_evaluation_review_v0_{compact}"


def _base(generated_ts: str, review_run_id: str) -> Dict[str, Any]:
    return {
        "generated_ts": generated_ts,
        "schema_version": SCHEMA_VERSION,
        "review_version": REVIEW_VERSION,
        "review_run_id": review_run_id,
    }


def _sheet_titles(service, spreadsheet_id: str) -> Set[str]:
    metadata = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    return {sheet["properties"]["title"] for sheet in metadata.get("sheets", [])}


def _safe_rows(service, titles: Set[str], sheet_name: str, missing: List[str]) -> List[Dict[str, Any]]:
    if sheet_name not in titles:
        missing.append(sheet_name)
        return []
    try:
        return _sheet_to_rows(service, DIAGNOSTICS_SPREADSHEET_ID, sheet_name)
    except Exception:
        missing.append(sheet_name)
        return []


def _rate_delta(row: Dict[str, Any], field: str) -> Optional[float]:
    return _float(row.get(field))


def _sample_warning(count: Any, threshold: int = 30) -> str:
    return "TRUE" if _int(count) < threshold else "FALSE"


def _signal_discipline(row: Dict[str, Any]) -> str:
    direction_delta = _rate_delta(row, "direction_match_rate_delta")
    overall_delta = _rate_delta(row, "overall_ok_rate_delta")
    false_delta = _rate_delta(row, "false_signal_rate_delta")
    positives = 0
    negatives = 0
    if direction_delta is not None:
        positives += int(direction_delta > 0)
        negatives += int(direction_delta < 0)
    if overall_delta is not None:
        positives += int(overall_delta > 0)
        negatives += int(overall_delta < 0)
    if false_delta is not None:
        positives += int(false_delta < 0)
        negatives += int(false_delta > 0)
    if positives >= 2 and negatives == 0:
        return "TREATMENT_IMPROVED"
    if negatives >= 2 and positives == 0:
        return "TREATMENT_WEAKENED"
    if positives or negatives:
        return "MIXED"
    return "NO_CLEAR_CHANGE"


def _classification(summary: Dict[str, Any], comparisons: Sequence[Dict[str, Any]]) -> str:
    direction = _float(summary.get("direction_match_rate")) or 0
    overall = _float(summary.get("overall_ok_rate")) or 0
    deltas = [_float(row.get("direction_match_rate_delta")) for row in comparisons]
    positive = sum(1 for val in deltas if val is not None and val > 0)
    negative = sum(1 for val in deltas if val is not None and val < 0)
    if direction == 0 and overall == 0:
        return "NO_ACCURACY_SIGNAL"
    if negative > positive and overall < 0.15:
        return "MIXED_ACCURACY_SIGNAL"
    if direction >= 0.55 and overall >= 0.20:
        return "MODERATE_ACCURACY_SIGNAL"
    return "WEAK_ACCURACY_SIGNAL"


def _source_behavior_hypothesis(accuracy_hypothesis_id: str) -> str:
    return {
        "ACC_HYP_USDJPY_TREND_DIRECTIONAL_ALIGNMENT": "HYP_USDJPY_TREND_REASONING",
        "ACC_HYP_PACK_B_TARGET_STATE_SIGNAL_DISCIPLINE": "HYP_A_TO_B_TARGET_STATE_VALUE",
        "ACC_HYP_OPENAI_STABLE_CAUSAL_REWRITE_TESTBED": "HYP_OPENAI_CAUSAL_STABLE",
    }.get(accuracy_hypothesis_id, "")


def _hypothesis_status(exp: Dict[str, Any], comparisons: Sequence[Dict[str, Any]]) -> Tuple[str, str, str, str, str, str]:
    experiment_id = _norm(exp.get("experiment_id"))
    direction = _float(exp.get("direction_match_rate")) or 0
    overall = _float(exp.get("overall_ok_rate")) or 0
    related = [row for row in comparisons if _norm(row.get("experiment_id")) == experiment_id]
    direction_deltas = [_float(row.get("direction_match_rate_delta")) for row in related]
    overall_deltas = [_float(row.get("overall_ok_rate_delta")) for row in related]
    false_deltas = [_float(row.get("false_signal_rate_delta")) for row in related]
    positive_overall = any(val is not None and val > 0 for val in overall_deltas)
    negative_direction_count = sum(1 for val in direction_deltas if val is not None and val < 0)
    false_worse_count = sum(1 for val in false_deltas if val is not None and val > 0)

    if experiment_id == "ACC_EXP_OPENAI_STABLE_CAUSAL_REWRITE_TESTBED":
        if positive_overall and _int(exp.get("invalid_outputs")) == 0:
            return (
                "TRANSFER_PARTIALLY_SUPPORTED",
                "PARTIALLY_SUPPORTED",
                "PROMOTE_TO_REPLICATION",
                "Replicate OpenAI as a clean testbed; do not treat as provider superiority.",
                "OpenAI remained invalid-free and one OpenAI A/B comparison improved overall_ok, but direction deltas weakened.",
                "candidate accuracy signal, replication needed",
            )
        return ("TRANSFER_INCONCLUSIVE", "INCONCLUSIVE", "KEEP_AS_CANDIDATE", "Retest with more rows.", "Clean output, but accuracy signal is weak.", "inconclusive")

    if negative_direction_count >= len(related) and related:
        return (
            "TRANSFER_NOT_SUPPORTED",
            "WEAKENED",
            "REVISE_AND_RETEST",
            "Revise hypothesis before replication; behavior did not translate into directional gains.",
            "Treatment direction deltas weakened against Pack A and false-signal rates increased.",
            "behavior strong, accuracy weak or negative",
        )
    if direction > 0.45 and overall > 0.10:
        return (
            "TRANSFER_WEAK",
            "PARTIALLY_SUPPORTED",
            "KEEP_AS_CANDIDATE",
            "Keep as candidate but require stronger paired-comparison support.",
            "Experiment-level rate is comparatively stronger, but paired comparisons remain mixed.",
            "weak candidate accuracy signal",
        )
    return (
        "TRANSFER_INCONCLUSIVE",
        "INCONCLUSIVE",
        "HOLD_DUE_LIMITATIONS",
        "Hold pending larger sample or metric review.",
        "Insufficient evidence for transfer.",
        "sample-limited",
    )


def _build_review_rows(generated_ts: str, review_run_id: str, summary: Dict[str, Any], accuracy_classification: str) -> List[Dict[str, Any]]:
    areas = [
        ("overall_accuracy_signal", "PASS_WITH_WARNINGS", "Behavior-confirmed patterns produced measurable but weak/mixed accuracy evidence."),
        ("direction_result", "PASS_WITH_WARNINGS", "Direction match rate is below a simple 0.50 directional reference and needs replication/context."),
        ("overall_ok_result", "NEEDS_REVIEW", "Overall OK is very low; this may reflect strict metric design, weak forecasts, or both."),
        ("governance", "PASS", "No provider calls, reruns, production writes, or result modifications occurred."),
        ("next_phase", "PASS_WITH_WARNINGS", "Hypothesis revision is favored before replication or production consideration."),
    ]
    rows = []
    for area, status, conclusion in areas:
        row = _base(generated_ts, review_run_id)
        row.update(
            {
                "review_area": area,
                "review_status": status,
                "evidence_scope": "Phase 9A-5F controlled accuracy evaluation",
                "experiments_reviewed": summary.get("experiments_executed"),
                "eligible_rows_evaluated": summary.get("eligible_rows_evaluated"),
                "comparison_pairs_evaluated": summary.get("comparison_pairs_evaluated"),
                "metrics_reviewed": summary.get("metrics_calculated"),
                "direction_denominator": summary.get("direction_denominator"),
                "direction_correct_count": summary.get("direction_correct_count"),
                "direction_match_rate": summary.get("direction_match_rate"),
                "overall_denominator": summary.get("overall_denominator"),
                "overall_ok_count": summary.get("overall_ok_count"),
                "overall_ok_rate": summary.get("overall_ok_rate"),
                "accuracy_signal_classification": accuracy_classification,
                "review_conclusion": conclusion,
                "recommended_next_action": "PROCEED_TO_PHASE9A5R_HYPOTHESIS_REVISION",
                "production_excluded": "TRUE",
                "notes": "Scientific interpretation only; no production or routing implication.",
            }
        )
        rows.append(row)
    return rows


def _build_hypothesis_rows(
    generated_ts: str,
    review_run_id: str,
    experiments: Sequence[Dict[str, Any]],
    comparisons: Sequence[Dict[str, Any]],
    metrics: Sequence[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    rows = []
    metrics_by_exp: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    comparisons_by_exp: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for metric in metrics:
        metrics_by_exp[_norm(metric.get("experiment_id"))].append(metric)
    for comp in comparisons:
        comparisons_by_exp[_norm(comp.get("experiment_id"))].append(comp)
    for exp in experiments:
        experiment_id = _norm(exp.get("experiment_id"))
        hypothesis_id = _norm(exp.get("accuracy_hypothesis_id"))
        transfer, support, rec_status, rec_action, interpretation, notes = _hypothesis_status(exp, comparisons_by_exp[experiment_id])
        primary_metrics = [m for m in metrics_by_exp[experiment_id] if _norm(m.get("metric_name")) in {"direction_match_rate", "false_signal_rate"}]
        secondary_metrics = [m for m in metrics_by_exp[experiment_id] if _norm(m.get("metric_name")) not in {"direction_match_rate", "false_signal_rate"}]
        comp_summary = "; ".join(
            f"{c.get('comparison_id')}: dir_delta={c.get('direction_match_rate_delta')}, overall_delta={c.get('overall_ok_rate_delta')}, false_delta={c.get('false_signal_rate_delta')}"
            for c in comparisons_by_exp[experiment_id]
        )
        row = _base(generated_ts, review_run_id)
        row.update(
            {
                "accuracy_hypothesis_id": hypothesis_id,
                "source_behavior_hypothesis_id": _source_behavior_hypothesis(hypothesis_id),
                "experiment_id": experiment_id,
                "experiment_result_direction_rate": exp.get("direction_match_rate"),
                "experiment_result_overall_rate": exp.get("overall_ok_rate"),
                "primary_metric_result_summary": _truncate_text("; ".join(f"{m.get('comparison_id')} {m.get('metric_name')}={m.get('metric_value')}" for m in primary_metrics), 1000),
                "secondary_metric_result_summary": _truncate_text("; ".join(f"{m.get('comparison_id')} {m.get('metric_name')}={m.get('metric_value') or m.get('metric_delta')}" for m in secondary_metrics), 1000),
                "comparison_evidence_summary": _truncate_text(comp_summary, 1000),
                "behavior_to_accuracy_transfer_status": transfer,
                "hypothesis_support_status": support,
                "sample_size_warning": _sample_warning(exp.get("eligible_rows_evaluated")),
                "invalid_output_impact": "NONE" if _int(exp.get("invalid_outputs")) == 0 else f"{exp.get('invalid_outputs')} invalid/excluded impacts",
                "interpretation": interpretation,
                "recommended_status": rec_status,
                "recommended_next_action": rec_action,
                "production_excluded": "TRUE",
                "notes": notes,
            }
        )
        rows.append(row)
    return rows


def _build_behavior_vs_accuracy_rows(
    generated_ts: str,
    review_run_id: str,
    behavior_rows: Sequence[Dict[str, Any]],
    hypothesis_rows: Sequence[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    behavior_by_id = {_norm(row.get("hypothesis_id")): row for row in behavior_rows}
    rows = []
    for hyp in hypothesis_rows:
        behavior_id = _norm(hyp.get("source_behavior_hypothesis_id"))
        behavior = behavior_by_id.get(behavior_id, {})
        transfer = _norm(hyp.get("behavior_to_accuracy_transfer_status"))
        if transfer == "TRANSFER_PARTIALLY_SUPPORTED":
            alignment = "BEHAVIOR_AND_ACCURACY_ALIGNED"
            transfer_result = "yes, partially"
        elif transfer == "TRANSFER_NOT_SUPPORTED":
            alignment = "BEHAVIOR_STRONG_ACCURACY_NEGATIVE"
            transfer_result = "no"
        elif transfer == "TRANSFER_WEAK":
            alignment = "BEHAVIOR_STRONG_ACCURACY_WEAK"
            transfer_result = "mixed"
        else:
            alignment = "BEHAVIOR_STRONG_ACCURACY_INCONCLUSIVE"
            transfer_result = "unclear"
        row = _base(generated_ts, review_run_id)
        row.update(
            {
                "behavior_hypothesis_id": behavior_id,
                "behavior_generalization_status": _norm(behavior.get("generalization_status")),
                "accuracy_hypothesis_id": _norm(hyp.get("accuracy_hypothesis_id")),
                "behavior_evidence_summary": _truncate_text(_norm(behavior.get("supporting_evidence_summary")), 750),
                "accuracy_result_summary": f"direction={hyp.get('experiment_result_direction_rate')}; overall={hyp.get('experiment_result_overall_rate')}; status={hyp.get('hypothesis_support_status')}",
                "transfer_result": transfer_result,
                "behavior_accuracy_alignment": alignment,
                "interpretation": _norm(hyp.get("interpretation")),
                "next_research_action": _norm(hyp.get("recommended_next_action")),
                "notes": "Behavior evidence remains separate from production readiness.",
            }
        )
        rows.append(row)
    return rows


def _build_pack_rows(generated_ts: str, review_run_id: str, comparisons: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows = []
    for comp in comparisons:
        result = _signal_discipline(comp)
        if result == "TREATMENT_IMPROVED":
            interpretation = "Treatment improved the frozen signal-discipline bundle in this comparison only."
            action = "Replication candidate; no production selection."
        elif result == "TREATMENT_WEAKENED":
            interpretation = "Treatment weakened the frozen signal-discipline bundle versus baseline."
            action = "Revise or retest before replication."
        elif result == "MIXED":
            interpretation = "Treatment moved metrics in mixed directions."
            action = "Retain as diagnostic evidence; avoid pack conclusion."
        else:
            interpretation = "No clear metric movement."
            action = "Inconclusive."
        row = _base(generated_ts, review_run_id)
        row.update(
            {
                "comparison_id": comp.get("comparison_id"),
                "baseline_pack": comp.get("baseline_pack_level"),
                "treatment_pack": comp.get("treatment_pack_level"),
                "provider_scope": comp.get("provider_scope"),
                "pair_count": comp.get("comparison_pairs_evaluated"),
                "direction_rate_baseline": comp.get("baseline_direction_match_rate"),
                "direction_rate_treatment": comp.get("treatment_direction_match_rate"),
                "direction_delta": comp.get("direction_match_rate_delta"),
                "overall_rate_baseline": comp.get("baseline_overall_ok_rate"),
                "overall_rate_treatment": comp.get("treatment_overall_ok_rate"),
                "overall_delta": comp.get("overall_ok_rate_delta"),
                "signal_discipline_result": result,
                "interpretation": interpretation,
                "sample_size_warning": _sample_warning(comp.get("comparison_pairs_evaluated")),
                "recommended_action": action,
                "production_excluded": "TRUE",
                "notes": "Diagnostic pack comparison only; no pack selection.",
            }
        )
        rows.append(row)
    return rows


def _build_provider_rows(
    generated_ts: str,
    review_run_id: str,
    eval_rows: Sequence[Dict[str, Any]],
    invalid_rows: Sequence[Dict[str, Any]],
    behavior_provider_rows: Sequence[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    by_provider: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    invalid_by_provider = Counter(_norm(row.get("provider")) for row in invalid_rows if _norm(row.get("provider")))
    behavior_by_provider = {_norm(row.get("provider")): row for row in behavior_provider_rows}
    for row in eval_rows:
        by_provider[_norm(row.get("provider"))].append(row)
    rows = []
    for provider, provider_rows in sorted(by_provider.items()):
        direction_rows = [row for row in provider_rows if _bool(row.get("included_in_direction_denominator"))]
        overall_rows = [row for row in provider_rows if _bool(row.get("included_in_overall_denominator"))]
        direction_correct = sum(1 for row in direction_rows if _bool(row.get("direction_correct")))
        overall_ok = sum(1 for row in overall_rows if _bool(row.get("overall_ok")))
        behavior = behavior_by_provider.get(provider, {})
        if _int(invalid_by_provider[provider]) > 0 and provider == "Gemini":
            interpretation = "behavior_sensitive_but_invalid_limited"
        elif provider == "OpenAI":
            interpretation = "output_stable_and_candidate_for_replication"
        else:
            interpretation = "inconclusive_due_sample"
        row = _base(generated_ts, review_run_id)
        row.update(
            {
                "provider": provider,
                "eligible_rows_evaluated": len(provider_rows),
                "invalid_outputs": invalid_by_provider[provider],
                "direction_denominator": len(direction_rows),
                "direction_correct_count": direction_correct,
                "direction_match_rate": _fmt(direction_correct / len(direction_rows)) if direction_rows else "",
                "overall_denominator": len(overall_rows),
                "overall_ok_count": overall_ok,
                "overall_ok_rate": _fmt(overall_ok / len(overall_rows)) if overall_rows else "",
                "behavior_profile_summary": _truncate_text(_norm(behavior.get("generalization_conclusion")) or _norm(behavior.get("provider_behavior_classification")), 500),
                "accuracy_profile_summary": f"direction={_fmt(direction_correct / len(direction_rows)) if direction_rows else ''}; overall={_fmt(overall_ok / len(overall_rows)) if overall_rows else ''}",
                "interpretation": interpretation,
                "provider_ranking_forbidden": "TRUE",
                "production_routing_forbidden": "TRUE",
                "notes": "Provider rows describe diagnostic evidence only and must not be ranked for production.",
            }
        )
        rows.append(row)
    return rows


def _build_metric_rows(generated_ts: str, review_run_id: str, metrics: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows = []
    for metric in metrics:
        denominator = _int(metric.get("denominator_count"))
        if denominator < 10:
            risk = "HIGH"
            recommendation = "Do not interpret without additional sample."
        elif _norm(metric.get("metric_name")) == "confidence_calibration_proxy":
            risk = "MEDIUM"
            recommendation = "Use as diagnostic proxy only; consider calibration design repair."
        else:
            risk = "MEDIUM"
            recommendation = "Use in replication design with frozen denominator rules."
        row = _base(generated_ts, review_run_id)
        row.update(
            {
                "metric_id": metric.get("metric_id"),
                "metric_name": metric.get("metric_name"),
                "metric_value_or_summary": metric.get("metric_value"),
                "denominator": metric.get("denominator_count"),
                "numerator": metric.get("numerator_count"),
                "experiment_id": metric.get("experiment_id"),
                "comparison_id": metric.get("comparison_id"),
                "metric_interpretation": _truncate_text(f"value={metric.get('metric_value')}; delta={metric.get('metric_delta')}; status={metric.get('metric_status')}", 800),
                "risk_of_overinterpretation": risk,
                "next_use_recommendation": recommendation,
                "notes": "Metric reviewed without changing calculation or eligibility.",
            }
        )
        rows.append(row)
    return rows


def _build_limitation_rows(generated_ts: str, review_run_id: str, summary: Dict[str, Any]) -> List[Dict[str, Any]]:
    all_hyp = "ACC_HYP_USDJPY_TREND_DIRECTIONAL_ALIGNMENT|ACC_HYP_PACK_B_TARGET_STATE_SIGNAL_DISCIPLINE|ACC_HYP_OPENAI_STABLE_CAUSAL_REWRITE_TESTBED"
    rows_data = [
        ("small_sample_size", "Small sample size", "Only 145 eligible rows and 87 comparison pairs are available.", all_hyp, "ALL", "HIGH", "Limits strength of any support/rejection claim.", "Run replication design before production interpretation.", "FALSE"),
        ("minimum_sample_warning_count", "Minimum sample warnings", "Some metric rows remain below preferred denominator thresholds.", all_hyp, "ALL", "MEDIUM", "Metric-level interpretation is uneven.", "Carry warnings into replication design.", "FALSE"),
        ("invalid_outputs", "Invalid outputs", f"{summary.get('invalid_outputs')} unique invalid outputs affected denominator composition.", all_hyp, "ALL", "MEDIUM", "Invalid-output exclusions may bias provider/pack coverage.", "Preserve invalid-output audit and avoid imputation.", "FALSE"),
        ("provider_503_failures", "Provider 503 failures", "Gemini 503 failures are visible in invalid-output results.", "ACC_HYP_USDJPY_TREND_DIRECTIONAL_ALIGNMENT|ACC_HYP_PACK_B_TARGET_STATE_SIGNAL_DISCIPLINE", "pack-level comparisons", "MEDIUM", "Provider availability may limit comparison balance.", "Separate provider availability from accuracy signal.", "FALSE"),
        ("anthropic_truncated_json", "Anthropic truncated JSON", "Historical Anthropic later-pack invalid-output risk remains relevant.", "ACC_HYP_USDJPY_TREND_DIRECTIONAL_ALIGNMENT", "A/D/E comparisons", "MEDIUM", "Can limit later-pack treatment evidence.", "Continue invalid-output isolation.", "FALSE"),
        ("outcome_matching_assumptions", "Outcome matching assumptions", "Phase 9A-5F used exact country + release_ts matching into Evaluation_Rows.", all_hyp, "ALL", "HIGH", "If matching semantics are revised, accuracy rates may change.", "Review matching design before replication.", "FALSE"),
        ("no_signal_proxy_definition", "No-signal proxy definition", "No-signal correctness depends on flat outcome proxy.", all_hyp, "no_signal_correctness", "HIGH", "No-signal results may be sensitive to flat/no-reaction threshold design.", "Design no-signal proxy repair or sensitivity test.", "FALSE"),
        ("overall_ok_stringency", "Overall OK stringency", "Overall OK requires direction/no-signal correctness and movement-range discipline.", all_hyp, "overall_ok", "HIGH", "Very low overall_ok may reflect strictness, weak forecasts, or both.", "Review overall_ok definition before production use.", "FALSE"),
        ("direction_denominator_smaller_than_overall", "Direction denominator smaller than overall", "Direction denominator excludes no-signal rows while overall includes all evaluated rows.", all_hyp, "ALL", "MEDIUM", "Direction and overall rates are not directly comparable denominators.", "Report denominator definitions beside all metrics.", "FALSE"),
        ("pack_d_pack_e_ambiguity", "Pack D / Pack E ambiguity", "Pack E remains exploratory and behaviorally ambiguous.", "ACC_HYP_USDJPY_TREND_DIRECTIONAL_ALIGNMENT", "A_E_EXPLORATORY", "MEDIUM", "Pack E comparisons should not drive production pack decisions.", "Keep Pack E exploratory in replication.", "FALSE"),
        ("behavior_not_equal_accuracy", "Behavior is not accuracy", "Strong behavior generalization did not clearly transfer into accuracy gains.", all_hyp, "ALL", "HIGH", "Behavioral activation should not be treated as forecast quality.", "Revise behavior-to-accuracy hypotheses.", "FALSE"),
        ("single_month_market_regime", "Single-month market regime", "Tier 2 uses May 2024 sessions only.", all_hyp, "ALL", "HIGH", "Results may be market-regime specific.", "Replicate across different months/regimes.", "FALSE"),
    ]
    rows = []
    for limitation_id, name, desc, hypotheses, experiments, severity, impact, mitigation, blocks in rows_data:
        row = _base(generated_ts, review_run_id)
        row.update(
            {
                "limitation_id": limitation_id,
                "limitation_name": name,
                "description": desc,
                "affected_hypotheses": hypotheses,
                "affected_experiments": experiments,
                "severity": severity,
                "impact_on_interpretation": impact,
                "recommended_mitigation": mitigation,
                "blocks_next_phase": blocks,
                "notes": "Limitation blocks production interpretation, not necessarily research continuation.",
            }
        )
        rows.append(row)
    return rows


def _build_governance_rows(generated_ts: str, review_run_id: str) -> List[Dict[str, Any]]:
    checks = [
        ("GOV_PROVIDER_CALLS", "provider_calls_performed", "0", "0"),
        ("GOV_FORECAST_GENERATION", "forecast_generation_performed", "0", "0"),
        ("GOV_PROVIDER_RERUN", "provider_rerun_count", "0", "0"),
        ("GOV_EVALUATION_RERUN", "evaluation_rerun_count", "0", "0"),
        ("GOV_RESULTS_MODIFIED", "accuracy_results_modified", "0", "0"),
        ("GOV_PRODUCTION_BEHAVIOR", "production_behavior_change_count", "0", "0"),
        ("GOV_PRODUCTION_SHEET", "production_sheet_write_count", "0", "0"),
        ("GOV_ROUTING", "routing_changes", "FALSE", "FALSE"),
        ("GOV_WEIGHTING", "weighting_changes", "FALSE", "FALSE"),
        ("GOV_CALIBRATION", "calibration_changes", "FALSE", "FALSE"),
        ("GOV_ENSEMBLE", "ensemble_changes", "FALSE", "FALSE"),
        ("GOV_PROVIDER_RANKING", "provider_ranking_recommended", "FALSE", "FALSE"),
        ("GOV_PRODUCTION_RECOMMENDATION", "production_recommendation_made", "FALSE", "FALSE"),
    ]
    rows = []
    for check_id, name, expected, actual in checks:
        row = _base(generated_ts, review_run_id)
        row.update(
            {
                "check_id": check_id,
                "check_name": name,
                "expected_value": expected,
                "actual_value": actual,
                "status": "PASS" if expected == actual else "FAIL",
                "notes": "Review phase governance check; no result mutation or production change.",
            }
        )
        rows.append(row)
    return rows


def _build_recommendation_rows(generated_ts: str, review_run_id: str) -> List[Dict[str, Any]]:
    data = [
        ("REC_REVISION", "REVISE_HYPOTHESIS", "Proceed to hypothesis revision before replication.", "Behavior effects did not clearly transfer into accuracy gains under frozen metrics.", "Phase 9A-5F results|Phase 9A-5G review", "", "HIGH", "Primary recommended path."),
        ("REC_METRIC_REVIEW", "METRIC_REPAIR", "Review overall_ok and no-signal proxy strictness.", "Overall OK is 14/145 and may combine metric strictness with forecast weakness.", "Controlled_Accuracy_Evaluation|Metric_Interpretation_Review", "", "HIGH", "Metric repair should not mutate Phase 9A-5F results."),
        ("REC_REPLICATION", "REPLICATION", "Replicate only revised hypotheses with frozen or explicitly repaired metrics.", "OpenAI A/B shows a mixed partial candidate, but no hypothesis is fully supported.", "Revised hypothesis design", "current hypotheses require revision", "MEDIUM", "No production use."),
        ("REC_SAMPLE", "ADDITIONAL_SAMPLE", "Add cross-month controlled accuracy samples after revision.", "Single May 2024 regime limits generality.", "Revised protocol|new approved sample", "hypothesis revision pending", "MEDIUM", "Additional sample must remain diagnostic-only."),
    ]
    rows = []
    for rec_id, rec_type, recommendation, rationale, required, blocked, priority, notes in data:
        row = _base(generated_ts, review_run_id)
        row.update(
            {
                "recommendation_id": rec_id,
                "recommendation_type": rec_type,
                "recommendation": recommendation,
                "rationale": rationale,
                "required_inputs": required,
                "blocked_by": blocked,
                "priority": priority,
                "notes": notes,
            }
        )
        rows.append(row)
    return rows


def _upsert_registry_rows(service) -> Dict[str, int]:
    headers = _ensure_sheet(service, PROJECT_OVERVIEWS_SPREADSHEET_ID, REGISTRY_SHEET, REGISTRY_HEADERS)
    rows = _sheet_to_rows(service, PROJECT_OVERVIEWS_SPREADSHEET_ID, REGISTRY_SHEET)
    now = _iso_now()
    by_id = {_upper(row.get("logical_sheet_id")): i + 2 for i, row in enumerate(rows)}
    existing_by_id = {_upper(row.get("logical_sheet_id")): row for row in rows}
    registry_rows = [
        ("CONTROLLED_ACCURACY_EVALUATION_REVIEW", OUTPUT_REVIEW, "controlled_accuracy_evaluation_review"),
        ("ACCURACY_HYPOTHESIS_REVIEW", OUTPUT_HYPOTHESIS, "accuracy_hypothesis_review"),
        ("BEHAVIOR_VS_ACCURACY_REVIEW", OUTPUT_BEHAVIOR_VS_ACCURACY, "behavior_vs_accuracy_review"),
        ("PACK_COMPARISON_ACCURACY_REVIEW", OUTPUT_PACK, "pack_comparison_accuracy_review"),
        ("PROVIDER_ACCURACY_REVIEW", OUTPUT_PROVIDER, "provider_accuracy_review"),
        ("METRIC_INTERPRETATION_REVIEW", OUTPUT_METRIC, "metric_interpretation_review"),
        ("ACCURACY_LIMITATION_AUDIT", OUTPUT_LIMITATION, "accuracy_limitation_audit"),
        ("ACCURACY_GOVERNANCE_REVIEW", OUTPUT_GOVERNANCE, "accuracy_governance_review"),
        ("ACCURACY_NEXT_PHASE_RECOMMENDATION", OUTPUT_RECOMMENDATION, "accuracy_next_phase_recommendation"),
        ("CONTROLLED_ACCURACY_EVALUATION_REVIEW_SUMMARY", OUTPUT_SUMMARY, "controlled_accuracy_evaluation_review_summary"),
    ]
    updates = []
    appended = 0
    for logical_id, sheet_name, role in registry_rows:
        key = _upper(logical_id)
        existing = existing_by_id.get(key, {})
        merged = {
            "logical_sheet_id": logical_id,
            "physical_sheet_name": sheet_name,
            "sheet_role": role,
            "workbook": "DIAGNOSTICS",
            "workbook_location": "DIAGNOSTICS",
            "workbook_id": DIAGNOSTICS_SPREADSHEET_ID,
            "category": REGISTRY_CATEGORY,
            "lifecycle": "active_shadow",
            "lifecycle_state": "ACTIVE",
            "owner_module": REGISTRY_OWNER_MODULE,
            "participates_in_rebuild": "TRUE",
            "read_only": "FALSE",
            "allow_creation": "TRUE",
            "created_phase": PHASE_LABEL,
            "notes": "Phase 9A-5G controlled accuracy evaluation review; scientific interpretation only.",
            "registry_created_ts": _norm(existing.get("registry_created_ts")) or now,
            "registry_last_verified_ts": now,
            "registry_migration_ts": _norm(existing.get("registry_migration_ts")),
            "registry_rename_ts": _norm(existing.get("registry_rename_ts")),
        }
        values = [merged.get(header, "") for header in headers]
        if key in by_id:
            row_number = by_id[key]
        else:
            appended += 1
            row_number = len(rows) + appended + 1
        updates.append({"range": f"'{REGISTRY_SHEET}'!A{row_number}:{_column_letter(len(headers))}{row_number}", "values": [values]})
    if updates:
        batch_update_values(service, PROJECT_OVERVIEWS_SPREADSHEET_ID, updates)
    return {"updated": len(registry_rows) - appended, "appended": appended}


def _parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build PreSignal v2.0 Phase 9A-5G controlled accuracy evaluation review.")
    return parser.parse_args(argv)


def build_controlled_accuracy_evaluation_review_v0(args: Optional[argparse.Namespace] = None) -> Dict[str, Any]:
    args = args or _parse_args()
    generated_ts = _iso_now()
    review_run_id = _run_id(generated_ts)
    service = build_sheets_service(load_credentials())
    titles = _sheet_titles(service, DIAGNOSTICS_SPREADSHEET_ID)
    missing_required: List[str] = []

    inputs_9a5f = {sheet: _safe_rows(service, titles, sheet, missing_required) for sheet in INPUT_9A5F}
    inputs_9a5e = {sheet: _safe_rows(service, titles, sheet, missing_required) for sheet in INPUT_9A5E}
    inputs_9a5d = {sheet: _safe_rows(service, titles, sheet, missing_required) for sheet in INPUT_9A5D}
    inputs_design = {sheet: _safe_rows(service, titles, sheet, missing_required) for sheet in INPUT_DESIGN}
    inputs_behavior = {sheet: _safe_rows(service, titles, sheet, missing_required) for sheet in INPUT_BEHAVIOR}
    if missing_required:
        raise RuntimeError(f"Missing required Phase 9A-5G inputs: {sorted(set(missing_required))}")
    _ = (inputs_9a5e, inputs_9a5d, inputs_design)

    summary = inputs_9a5f["Controlled_Accuracy_Evaluation_Summary"][-1]
    experiments = inputs_9a5f["Controlled_Accuracy_Experiment_Results"]
    comparisons = inputs_9a5f["Controlled_Accuracy_Comparison_Results"]
    metrics = inputs_9a5f["Controlled_Accuracy_Metric_Results"]
    eval_rows = inputs_9a5f["Controlled_Accuracy_Evaluation"]
    invalid_rows = inputs_9a5f["Controlled_Accuracy_Invalid_Output_Results"]
    source_governance = inputs_9a5f["Controlled_Accuracy_Governance_Audit"]
    if any(_norm(row.get("status")) != "PASS" for row in source_governance):
        raise RuntimeError("Phase 9A-5F governance was not clean; review blocked.")

    accuracy_class = _classification(summary, comparisons)
    review_rows = _build_review_rows(generated_ts, review_run_id, summary, accuracy_class)
    hypothesis_rows = _build_hypothesis_rows(generated_ts, review_run_id, experiments, comparisons, metrics)
    behavior_rows = _build_behavior_vs_accuracy_rows(
        generated_ts,
        review_run_id,
        inputs_behavior["Pack_Behavior_Tier2_Hypothesis_Generalization"],
        hypothesis_rows,
    )
    pack_rows = _build_pack_rows(generated_ts, review_run_id, comparisons)
    provider_rows = _build_provider_rows(
        generated_ts,
        review_run_id,
        eval_rows,
        invalid_rows,
        inputs_behavior["Pack_Behavior_Tier2_Provider_Generalization"],
    )
    metric_rows = _build_metric_rows(generated_ts, review_run_id, metrics)
    limitation_rows = _build_limitation_rows(generated_ts, review_run_id, summary)
    governance_rows = _build_governance_rows(generated_ts, review_run_id)
    recommendation_rows = _build_recommendation_rows(generated_ts, review_run_id)

    supported = sum(1 for row in hypothesis_rows if _norm(row.get("hypothesis_support_status")) == "SUPPORTED")
    partial = sum(1 for row in hypothesis_rows if _norm(row.get("hypothesis_support_status")) == "PARTIALLY_SUPPORTED")
    not_supported = sum(1 for row in hypothesis_rows if _norm(row.get("hypothesis_support_status")) in {"NOT_SUPPORTED", "WEAKENED"})
    inconclusive = sum(1 for row in hypothesis_rows if _norm(row.get("hypothesis_support_status")) in {"INCONCLUSIVE", "INVALID_OUTPUT_LIMITED"})
    retired = sum(1 for row in hypothesis_rows if _norm(row.get("recommended_status")) == "RETIRE_HYPOTHESIS")
    governance_failed = any(_norm(row.get("status")) != "PASS" for row in governance_rows)

    strongest_partial = "ACC_HYP_OPENAI_STABLE_CAUSAL_REWRITE_TESTBED_PARTIAL_REPLICATION_CANDIDATE" if partial else "NONE_FULLY_SUPPORTED"
    summary_rows = [
        {
            **_base(generated_ts, review_run_id),
            "build_status": "PASS_WITH_WARNINGS" if not governance_failed else "FAIL",
            "final_interpretation": "CONTROLLED_ACCURACY_REVIEW_READY_WITH_WARNINGS" if not governance_failed else "CONTROLLED_ACCURACY_REVIEW_BLOCKED",
            "experiments_reviewed": len(experiments),
            "hypotheses_reviewed": len(hypothesis_rows),
            "hypotheses_supported": supported,
            "hypotheses_partially_supported": partial,
            "hypotheses_not_supported": not_supported,
            "hypotheses_inconclusive": inconclusive,
            "hypotheses_retired": retired,
            "direction_denominator": summary.get("direction_denominator"),
            "direction_correct_count": summary.get("direction_correct_count"),
            "direction_match_rate": summary.get("direction_match_rate"),
            "overall_denominator": summary.get("overall_denominator"),
            "overall_ok_count": summary.get("overall_ok_count"),
            "overall_ok_rate": summary.get("overall_ok_rate"),
            "strongest_supported_hypothesis": strongest_partial,
            "strongest_pack_comparison_signal": "CMP_OPENAI_A_B_MIXED_OVERALL_POSITIVE_DIRECTION_NEGATIVE",
            "strongest_provider_accuracy_profile": "OpenAI_output_stable_partial_testbed_signal_not_provider_ranking",
            "highest_risk_limitation": "overall_ok_stringency",
            "primary_interpretation": "Behavior-confirmed patterns produced measurable but mixed/weak accuracy evidence; revise hypotheses and metrics before replication.",
            "provider_calls_performed": 0,
            "forecast_generation_performed": 0,
            "provider_rerun_count": 0,
            "evaluation_rerun_count": 0,
            "accuracy_results_modified": 0,
            "production_behavior_change_count": 0,
            "production_sheet_write_count": 0,
            "ready_for_replication_design": "FALSE",
            "ready_for_hypothesis_revision": "TRUE",
            "ready_for_production": "FALSE",
            "recommended_next_step": "PROCEED_TO_PHASE9A5R_HYPOTHESIS_REVISION",
            "notes": json.dumps(
                {
                    "no_accuracy_rerun": True,
                    "no_result_modification": True,
                    "no_production_recommendation": True,
                    "accuracy_signal_classification": accuracy_class,
                },
                sort_keys=True,
            ),
        }
    ]

    outputs = [
        (OUTPUT_REVIEW, REVIEW_HEADERS, review_rows),
        (OUTPUT_HYPOTHESIS, HYPOTHESIS_HEADERS, hypothesis_rows),
        (OUTPUT_BEHAVIOR_VS_ACCURACY, BEHAVIOR_VS_ACCURACY_HEADERS, behavior_rows),
        (OUTPUT_PACK, PACK_HEADERS, pack_rows),
        (OUTPUT_PROVIDER, PROVIDER_HEADERS, provider_rows),
        (OUTPUT_METRIC, METRIC_HEADERS, metric_rows),
        (OUTPUT_LIMITATION, LIMITATION_HEADERS, limitation_rows),
        (OUTPUT_GOVERNANCE, GOVERNANCE_HEADERS, governance_rows),
        (OUTPUT_RECOMMENDATION, RECOMMENDATION_HEADERS, recommendation_rows),
        (OUTPUT_SUMMARY, SUMMARY_HEADERS, summary_rows),
    ]
    for sheet_name, headers, rows in outputs:
        actual_headers = _ensure_sheet(service, DIAGNOSTICS_SPREADSHEET_ID, sheet_name, headers)
        _write_rows(service, DIAGNOSTICS_SPREADSHEET_ID, sheet_name, actual_headers, rows)

    registry = _upsert_registry_rows(service)
    return {
        "build_status": summary_rows[0]["build_status"],
        "final_interpretation": summary_rows[0]["final_interpretation"],
        "file_created": "automation/build_controlled_accuracy_evaluation_review_v0.py",
        "sheets_written": {sheet_name: len(rows) for sheet_name, _, rows in outputs},
        "experiments_reviewed": len(experiments),
        "hypotheses_reviewed": len(hypothesis_rows),
        "hypotheses_supported": supported,
        "hypotheses_partially_supported": partial,
        "hypotheses_not_supported": not_supported,
        "hypotheses_inconclusive": inconclusive,
        "hypotheses_retired": retired,
        "direction_denominator": summary.get("direction_denominator"),
        "direction_correct_count": summary.get("direction_correct_count"),
        "direction_match_rate": summary.get("direction_match_rate"),
        "overall_denominator": summary.get("overall_denominator"),
        "overall_ok_count": summary.get("overall_ok_count"),
        "overall_ok_rate": summary.get("overall_ok_rate"),
        "strongest_supported_hypothesis": strongest_partial,
        "strongest_pack_comparison_signal": "CMP_OPENAI_A_B_MIXED_OVERALL_POSITIVE_DIRECTION_NEGATIVE",
        "strongest_provider_accuracy_profile": "OpenAI_output_stable_partial_testbed_signal_not_provider_ranking",
        "highest_risk_limitation": "overall_ok_stringency",
        "primary_interpretation": summary_rows[0]["primary_interpretation"],
        "provider_calls_performed": 0,
        "forecast_generation_performed": 0,
        "provider_rerun_count": 0,
        "evaluation_rerun_count": 0,
        "accuracy_results_modified": 0,
        "production_behavior_change_count": 0,
        "production_sheet_write_count": 0,
        "ready_for_replication_design": False,
        "ready_for_hypothesis_revision": True,
        "ready_for_production": False,
        "recommended_next_step": "PROCEED_TO_PHASE9A5R_HYPOTHESIS_REVISION",
        "registry": registry,
    }


def main() -> None:
    result = build_controlled_accuracy_evaluation_review_v0()
    print(json.dumps(result, indent=2, ensure_ascii=True))


if __name__ == "__main__":
    main()
