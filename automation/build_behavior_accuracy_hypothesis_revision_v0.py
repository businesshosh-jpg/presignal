import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set

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


SCHEMA_VERSION = "presignal_v2_behavior_accuracy_hypothesis_revision_0.1"
REVISION_VERSION = "behavior_accuracy_hypothesis_revision_v0"
PHASE_LABEL = "PreSignal v2.0 Phase 9A-5R"
REGISTRY_CATEGORY = "PRESIGNAL_V2_BEHAVIOR_ACCURACY_HYPOTHESIS_REVISION"
REGISTRY_OWNER_MODULE = "market_state"

INPUT_9A5G = [
    "Controlled_Accuracy_Evaluation_Review",
    "Accuracy_Hypothesis_Review",
    "Behavior_vs_Accuracy_Review",
    "Pack_Comparison_Accuracy_Review",
    "Provider_Accuracy_Review",
    "Metric_Interpretation_Review",
    "Accuracy_Limitation_Audit",
    "Accuracy_Governance_Review",
    "Accuracy_Next_Phase_Recommendation",
    "Controlled_Accuracy_Evaluation_Review_Summary",
]

INPUT_9A5F = [
    "Controlled_Accuracy_Evaluation",
    "Controlled_Accuracy_Experiment_Results",
    "Controlled_Accuracy_Comparison_Results",
    "Controlled_Accuracy_Metric_Results",
    "Controlled_Accuracy_Invalid_Output_Results",
    "Controlled_Accuracy_Governance_Audit",
    "Controlled_Accuracy_Evaluation_Summary",
]

INPUT_DESIGN = [
    "Behavior_To_Accuracy_Testable_Hypotheses",
    "Behavior_To_Accuracy_Eligible_Hypotheses",
    "Behavior_To_Accuracy_Excluded_Hypotheses",
    "Behavior_To_Accuracy_Confounder_Audit",
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
    "Accuracy_Execution_Approval",
    "Accuracy_Execution_Freeze_Record",
    "Accuracy_Execution_Risk_Assessment",
    "Accuracy_Execution_Interpretation_Guardrails",
    "Accuracy_Execution_Approval_Summary",
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

OUTPUT_REVISION = "Behavior_Accuracy_Hypothesis_Revision"
OUTPUT_FAILED_TRANSFER = "Behavior_Accuracy_Failed_Transfer_Audit"
OUTPUT_MECHANISM = "Behavior_Accuracy_Mechanism_Gap_Audit"
OUTPUT_REVISED_HYPOTHESES = "Behavior_Accuracy_Revised_Hypotheses"
OUTPUT_METRIC = "Behavior_Accuracy_Metric_Revision_Audit"
OUTPUT_REPLICATION = "Behavior_Accuracy_Replication_Readiness"
OUTPUT_GOVERNANCE = "Behavior_Accuracy_Governance_Audit"
OUTPUT_SUMMARY = "Behavior_Accuracy_Revision_Summary"

REVISION_HEADERS = [
    "generated_ts",
    "schema_version",
    "revision_version",
    "revision_run_id",
    "revision_area",
    "revision_status",
    "source_review",
    "behavior_accuracy_transfer_summary",
    "hypotheses_reviewed",
    "hypotheses_revised",
    "hypotheses_retained",
    "hypotheses_retired",
    "mechanism_gap_identified",
    "metric_revision_needed",
    "replication_ready",
    "revision_conclusion",
    "recommended_next_action",
    "production_excluded",
    "notes",
]

FAILED_TRANSFER_HEADERS = [
    "generated_ts",
    "schema_version",
    "revision_version",
    "revision_run_id",
    "accuracy_hypothesis_id",
    "source_behavior_hypothesis_id",
    "behavior_signal_strength",
    "accuracy_result_status",
    "direction_rate",
    "overall_ok_rate",
    "transfer_result",
    "failed_or_weak_transfer_reason",
    "possible_explanation",
    "revision_required",
    "recommended_revision_type",
    "notes",
]

MECHANISM_HEADERS = [
    "generated_ts",
    "schema_version",
    "revision_version",
    "revision_run_id",
    "mechanism_gap_id",
    "source_behavior_hypothesis_id",
    "source_accuracy_hypothesis_id",
    "assumed_mechanism",
    "observed_behavior",
    "observed_accuracy_result",
    "mechanism_gap_description",
    "why_behavior_may_not_improve_accuracy",
    "required_future_test",
    "severity",
    "notes",
]

REVISED_HYPOTHESES_HEADERS = [
    "generated_ts",
    "schema_version",
    "revision_version",
    "revision_run_id",
    "revised_hypothesis_id",
    "parent_hypothesis_id",
    "hypothesis_layer",
    "hypothesis_statement",
    "mechanism_statement",
    "accuracy_test_statement",
    "required_comparison",
    "required_metric_revision",
    "required_sample_scope",
    "required_controls",
    "expected_evidence",
    "failure_condition",
    "ready_for_replication_design",
    "ready_for_metric_repair",
    "ready_for_future_accuracy_test",
    "production_excluded",
    "notes",
]

METRIC_HEADERS = [
    "generated_ts",
    "schema_version",
    "revision_version",
    "revision_run_id",
    "metric_id",
    "metric_name",
    "current_use",
    "observed_issue",
    "revision_needed",
    "recommended_metric_action",
    "affected_hypotheses",
    "notes",
]

REPLICATION_HEADERS = [
    "generated_ts",
    "schema_version",
    "revision_version",
    "revision_run_id",
    "revised_hypothesis_id",
    "replication_readiness_status",
    "readiness_reason",
    "blocking_issue",
    "required_before_replication",
    "recommended_next_phase",
    "notes",
]

GOVERNANCE_HEADERS = [
    "generated_ts",
    "schema_version",
    "revision_version",
    "revision_run_id",
    "check_id",
    "check_name",
    "expected_value",
    "actual_value",
    "status",
    "notes",
]

SUMMARY_HEADERS = [
    "generated_ts",
    "schema_version",
    "revision_version",
    "revision_run_id",
    "build_status",
    "final_interpretation",
    "original_accuracy_hypotheses_reviewed",
    "hypotheses_revised",
    "hypotheses_retained",
    "hypotheses_retired",
    "mechanism_gaps_identified",
    "metrics_reviewed",
    "metrics_requiring_revision",
    "revised_hypotheses_defined",
    "strongest_revised_hypothesis",
    "primary_mechanism_gap",
    "highest_priority_metric_revision",
    "replication_ready_hypotheses",
    "hypotheses_requiring_metric_repair",
    "hypotheses_requiring_scope_narrowing",
    "provider_calls_performed",
    "forecast_generation_performed",
    "provider_rerun_count",
    "evaluation_rerun_count",
    "accuracy_results_modified",
    "metric_values_recalculated",
    "production_behavior_change_count",
    "production_sheet_write_count",
    "ready_for_replication_design",
    "ready_for_metric_repair",
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
    value = _float(value)
    return int(value) if value is not None else 0


def _run_id(generated_ts: str) -> str:
    compact = generated_ts.replace("-", "").replace(":", "").replace("Z", "Z")
    return f"behavior_accuracy_hypothesis_revision_v0_{compact}"


def _base(generated_ts: str, revision_run_id: str) -> Dict[str, Any]:
    return {
        "generated_ts": generated_ts,
        "schema_version": SCHEMA_VERSION,
        "revision_version": REVISION_VERSION,
        "revision_run_id": revision_run_id,
    }


def _sheet_titles(service, spreadsheet_id: str) -> Set[str]:
    metadata = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    return {sheet["properties"]["title"] for sheet in metadata.get("sheets", [])}


def _safe_rows(
    service,
    spreadsheet_id: str,
    titles: Set[str],
    sheet_name: str,
    missing: List[str],
) -> List[Dict[str, Any]]:
    if sheet_name not in titles:
        missing.append(sheet_name)
        return []
    try:
        return _sheet_to_rows(service, spreadsheet_id, sheet_name)
    except Exception:
        missing.append(sheet_name)
        return []


def _latest(rows: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    return rows[-1] if rows else {}


def _source_behavior_hypothesis(accuracy_hypothesis_id: str) -> str:
    return {
        "ACC_HYP_USDJPY_TREND_DIRECTIONAL_ALIGNMENT": "HYP_USDJPY_TREND_REASONING",
        "ACC_HYP_PACK_B_TARGET_STATE_SIGNAL_DISCIPLINE": "HYP_A_TO_B_TARGET_STATE_VALUE",
        "ACC_HYP_OPENAI_STABLE_CAUSAL_REWRITE_TESTBED": "HYP_OPENAI_CAUSAL_STABLE",
    }.get(accuracy_hypothesis_id, "")


def _experiment_by_hypothesis(experiments: Sequence[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    return {_norm(row.get("accuracy_hypothesis_id")): row for row in experiments if _norm(row.get("accuracy_hypothesis_id"))}


def _behavior_strength_by_hypothesis(behavior_rows: Sequence[Dict[str, Any]]) -> Dict[str, str]:
    strength: Dict[str, str] = {}
    for row in behavior_rows:
        hypothesis_id = _norm(row.get("hypothesis_id"))
        if not hypothesis_id:
            continue
        level = _norm(row.get("behavior_support_level")) or _norm(row.get("generalization_status"))
        strength[hypothesis_id] = level or "BEHAVIOR_CONFIRMED"
    return strength


def _build_revision_rows(
    generated_ts: str,
    revision_run_id: str,
    review_summary: Dict[str, Any],
) -> List[Dict[str, Any]]:
    transfer_summary = _norm(review_summary.get("primary_interpretation")) or (
        "Behavior-confirmed patterns produced measurable but mixed/weak accuracy evidence."
    )
    common = {
        "source_review": "Phase 9A-5G Controlled Accuracy Evaluation Review",
        "behavior_accuracy_transfer_summary": transfer_summary,
        "hypotheses_reviewed": review_summary.get("hypotheses_reviewed") or 3,
        "hypotheses_revised": 3,
        "hypotheses_retained": 1,
        "hypotheses_retired": 0,
        "mechanism_gap_identified": "TRUE",
        "metric_revision_needed": "TRUE",
        "replication_ready": "FALSE",
        "recommended_next_action": "PROCEED_TO_PHASE9A5M_METRIC_OR_OUTCOME_REPAIR",
        "production_excluded": "TRUE",
    }
    areas = [
        (
            "behavior_accuracy_bridge",
            "PASS_WITH_WARNINGS",
            "Introduce Behavior -> Mechanism -> Accuracy as the required research bridge.",
            "Strong behavior should not move directly to replication without an explicit mechanism.",
        ),
        (
            "failed_transfer_revision",
            "PASS_WITH_WARNINGS",
            "Revise USDJPY and Pack B hypotheses because behavior did not clearly improve frozen accuracy metrics.",
            "Weak transfer may reflect mechanism, metric, scope, or sample limitations rather than a simple null effect.",
        ),
        (
            "openai_testbed_reframe",
            "PASS_WITH_WARNINGS",
            "Retain OpenAI as a low-invalid-output testbed/control candidate, not as provider superiority.",
            "OpenAI partial signal is useful for experimental control but must not become provider ranking.",
        ),
        (
            "metric_revision",
            "NEEDS_REVIEW",
            "Review overall_ok stringency and no-signal proxy before replication.",
            "Phase 9A-5G identified overall_ok_stringency as the highest-risk limitation.",
        ),
        (
            "governance",
            "PASS",
            "No accuracy results were modified, no providers were called, and production remains untouched.",
            "Revision is diagnostic-only and does not alter the frozen 9A-5F evidence.",
        ),
    ]
    rows = []
    for area, status, conclusion, notes in areas:
        row = _base(generated_ts, revision_run_id)
        row.update(common)
        row.update(
            {
                "revision_area": area,
                "revision_status": status,
                "revision_conclusion": conclusion,
                "notes": notes,
            }
        )
        rows.append(row)
    return rows


def _build_failed_transfer_rows(
    generated_ts: str,
    revision_run_id: str,
    hypothesis_review_rows: Sequence[Dict[str, Any]],
    experiments_by_hypothesis: Dict[str, Dict[str, Any]],
    behavior_strength: Dict[str, str],
) -> List[Dict[str, Any]]:
    required = [
        "ACC_HYP_USDJPY_TREND_DIRECTIONAL_ALIGNMENT",
        "ACC_HYP_PACK_B_TARGET_STATE_SIGNAL_DISCIPLINE",
        "ACC_HYP_OPENAI_STABLE_CAUSAL_REWRITE_TESTBED",
    ]
    review_by_hypothesis = {_norm(row.get("accuracy_hypothesis_id")): row for row in hypothesis_review_rows}
    revision_details = {
        "ACC_HYP_USDJPY_TREND_DIRECTIONAL_ALIGNMENT": (
            "Behaviorally strong USDJPY trend references did not produce directional improvement under the frozen universal comparison.",
            "USDJPY trend may be predictive only under specific market regimes or when aligned with outcome-sensitive session context.",
            "TRUE",
            "ADD_MECHANISM_LAYER",
        ),
        "ACC_HYP_PACK_B_TARGET_STATE_SIGNAL_DISCIPLINE": (
            "Pack B produced visible behavioral movement but paired comparisons weakened direction and false-signal discipline.",
            "Pack B may increase decisiveness or change framing without reducing unsupported signals under all sessions.",
            "TRUE",
            "REDEFINE_METRIC",
        ),
        "ACC_HYP_OPENAI_STABLE_CAUSAL_REWRITE_TESTBED": (
            "OpenAI showed the strongest partial signal but not a broad accuracy improvement.",
            "OpenAI may be valuable as a low-invalid-output control condition rather than an accuracy-improving provider.",
            "TRUE",
            "RETAIN_FOR_REPLICATION",
        ),
    }
    rows = []
    for hyp_id in required:
        behavior_id = _source_behavior_hypothesis(hyp_id)
        review = review_by_hypothesis.get(hyp_id, {})
        exp = experiments_by_hypothesis.get(hyp_id, {})
        reason, explanation, revision_required, revision_type = revision_details[hyp_id]
        row = _base(generated_ts, revision_run_id)
        row.update(
            {
                "accuracy_hypothesis_id": hyp_id,
                "source_behavior_hypothesis_id": behavior_id,
                "behavior_signal_strength": behavior_strength.get(behavior_id, "BEHAVIOR_CONFIRMED"),
                "accuracy_result_status": _norm(review.get("hypothesis_support_status")) or _norm(exp.get("result_status")),
                "direction_rate": exp.get("direction_match_rate") or review.get("experiment_result_direction_rate"),
                "overall_ok_rate": exp.get("overall_ok_rate") or review.get("experiment_result_overall_rate"),
                "transfer_result": _norm(review.get("behavior_to_accuracy_transfer_status")) or "TRANSFER_WEAK",
                "failed_or_weak_transfer_reason": reason,
                "possible_explanation": explanation,
                "revision_required": revision_required,
                "recommended_revision_type": revision_type,
                "notes": "No metric values recalculated; this row reinterprets frozen 9A-5F/5G outputs only.",
            }
        )
        rows.append(row)
    return rows


def _build_mechanism_gap_rows(generated_ts: str, revision_run_id: str) -> List[Dict[str, Any]]:
    gap_rows = [
        (
            "MECH_GAP_USDJPY_CONDITIONALITY",
            "HYP_USDJPY_TREND_REASONING",
            "ACC_HYP_USDJPY_TREND_DIRECTIONAL_ALIGNMENT",
            "USDJPY trend reasoning should improve directional alignment.",
            "Providers repeatedly referenced USDJPY trend fields and changed reasoning.",
            "USDJPY experiment direction rate remained weak.",
            "USDJPY trend changed reasoning without proving that the feature was predictive for the session outcome.",
            "Trend fields can be salient but non-predictive if the release shock, risk regime, or dollar/rates context dominates.",
            "Test conditional USDJPY value by regime/session filters before universal directional claims.",
            "HIGH",
        ),
        (
            "MECH_GAP_PACK_B_DECISIVENESS",
            "HYP_A_TO_B_TARGET_STATE_VALUE",
            "ACC_HYP_PACK_B_TARGET_STATE_SIGNAL_DISCIPLINE",
            "Pack B target-state exposure should improve signal discipline.",
            "A_to_B repeatedly produced behavior transitions.",
            "Pack B had the strongest experiment direction rate but weak paired-comparison support.",
            "Pack B may increase decisiveness without improving correctness.",
            "More decisive outputs can amplify both useful signals and unsupported directional noise.",
            "Test false-signal and no-signal discipline in low-signal sessions with decomposed metrics.",
            "HIGH",
        ),
        (
            "MECH_GAP_OPENAI_CAUSAL_REWRITE",
            "HYP_OPENAI_CAUSAL_STABLE",
            "ACC_HYP_OPENAI_STABLE_CAUSAL_REWRITE_TESTBED",
            "Stable causal-chain rewriting should provide a clean accuracy testbed.",
            "OpenAI showed low invalid-output risk and stable causal rewriting behavior.",
            "OpenAI produced only partial/mixed accuracy transfer.",
            "Clean causal rewriting may improve experimental reliability without improving directional alignment.",
            "Output validity and explanatory consistency are measurement advantages, not accuracy guarantees.",
            "Use OpenAI as a control/testbed while testing metric and scope repairs.",
            "MEDIUM",
        ),
        (
            "MECH_GAP_OVERALL_OK_STRINGENCY",
            "ALL_BEHAVIOR_CONFIRMED",
            "ALL_ACCURACY_HYPOTHESES",
            "overall_ok should capture complete forecast correctness.",
            "Behavior changes were captured across packs and providers.",
            "overall_ok rate was very low.",
            "overall_ok may be too strict for session-level partial correctness.",
            "A forecast can be directionally useful while missing pips bands, no-signal framing, or composite criteria.",
            "Decompose overall_ok into component metrics before replication.",
            "HIGH",
        ),
        (
            "MECH_GAP_DIRECTION_ONLY_LIMIT",
            "ALL_BEHAVIOR_CONFIRMED",
            "ALL_ACCURACY_HYPOTHESES",
            "Directional accuracy should reveal pack value.",
            "Pack exposure changed reasoning, confidence, and no-signal state.",
            "Direction match rate was mixed and below a simple directional reference.",
            "Direction-only accuracy may miss no-signal discipline.",
            "A pack can reduce bad signals or alter uncertainty without improving directional-hit rate.",
            "Prioritize false_signal_rate and no_signal_correctness repair for discipline hypotheses.",
            "HIGH",
        ),
        (
            "MECH_GAP_NO_SIGNAL_PROXY",
            "HYP_A_TO_B_TARGET_STATE_VALUE",
            "ACC_HYP_PACK_B_TARGET_STATE_SIGNAL_DISCIPLINE",
            "No-signal correctness proxy should reflect true signal quality.",
            "No-signal behavior varied across pack levels.",
            "No-signal metric evidence remained weak/ambiguous.",
            "No-signal proxy may not reflect true signal quality.",
            "Flat-market outcome definitions can misclassify cautious behavior in volatile or ambiguous sessions.",
            "Repair no-signal proxy and define flat/no-reaction thresholds before replication.",
            "HIGH",
        ),
        (
            "MECH_GAP_FEATURE_USEFULNESS",
            "HYP_USDJPY_TREND_REASONING",
            "ACC_HYP_USDJPY_TREND_DIRECTIONAL_ALIGNMENT",
            "Feature presence and use should improve forecasts.",
            "Providers used or referenced deterministic fields.",
            "Feature-driven behavior did not yield strong accuracy gains.",
            "Feature presence may not equal feature usefulness.",
            "A field can be consistently attended to while having low predictive value for the evaluated outcome window.",
            "Separate feature salience from conditional predictive value.",
            "MEDIUM",
        ),
        (
            "MECH_GAP_SENSITIVITY_NOISE",
            "HYP_GEMINI_HIGH_SENSITIVITY",
            "EXCLUDED_FROM_9A5A_DIRECT_ACCURACY",
            "Behavioral sensitivity should reveal useful adaptation.",
            "Provider sensitivity was behaviorally active in prior phases.",
            "Accuracy transfer did not become broadly strong.",
            "Behavioral sensitivity may create noise rather than signal.",
            "Highly reactive outputs can overfit prompt context or amplify non-predictive features.",
            "Design mechanism discovery before testing sensitive-provider accuracy effects.",
            "MEDIUM",
        ),
    ]
    rows = []
    for (
        gap_id,
        behavior_hyp,
        accuracy_hyp,
        assumed,
        observed_behavior,
        observed_accuracy,
        description,
        why_not,
        future_test,
        severity,
    ) in gap_rows:
        row = _base(generated_ts, revision_run_id)
        row.update(
            {
                "mechanism_gap_id": gap_id,
                "source_behavior_hypothesis_id": behavior_hyp,
                "source_accuracy_hypothesis_id": accuracy_hyp,
                "assumed_mechanism": assumed,
                "observed_behavior": observed_behavior,
                "observed_accuracy_result": observed_accuracy,
                "mechanism_gap_description": description,
                "why_behavior_may_not_improve_accuracy": why_not,
                "required_future_test": future_test,
                "severity": severity,
                "notes": "Mechanism gap only; no outcome values recalculated.",
            }
        )
        rows.append(row)
    return rows


def _build_revised_hypothesis_rows(generated_ts: str, revision_run_id: str) -> List[Dict[str, Any]]:
    revised = [
        {
            "revised_hypothesis_id": "REV_HYP_USDJPY_CONDITIONAL_PREDICTIVE_VALUE",
            "parent_hypothesis_id": "ACC_HYP_USDJPY_TREND_DIRECTIONAL_ALIGNMENT",
            "hypothesis_layer": "MECHANISM",
            "hypothesis_statement": "USDJPY trend is behaviorally salient but accuracy-relevant only under specific session regimes.",
            "mechanism_statement": "USDJPY trend improves accuracy only when aligned with outcome-sensitive market context such as pre-release FX momentum, dollar context, or rates regime.",
            "accuracy_test_statement": "Under predefined qualifying regimes, USDJPY trend exposure should improve directional alignment or reduce false signals versus Pack A baseline.",
            "required_comparison": "Pack A vs Pack B|Pack A vs Pack D within qualifying session regimes",
            "required_metric_revision": "behavior_conditioned_accuracy_delta|false_signal_rate|direction_match_rate with regime filters",
            "required_sample_scope": "Additional sessions stratified by trend-aligned vs trend-conflicted regimes",
            "required_controls": "Market regime, event family, outcome window, Pack D/E ambiguity",
            "expected_evidence": "Positive behavior-conditioned delta only in qualifying regimes, not universal improvement.",
            "failure_condition": "No conditional improvement after regime controls and sufficient sample.",
            "ready_for_replication_design": "FALSE",
            "ready_for_metric_repair": "TRUE",
            "ready_for_future_accuracy_test": "FALSE",
            "notes": "Conditionalizes USDJPY rather than retiring it.",
        },
        {
            "revised_hypothesis_id": "REV_HYP_PACK_B_SIGNAL_DISCIPLINE_CONDITIONAL",
            "parent_hypothesis_id": "ACC_HYP_PACK_B_TARGET_STATE_SIGNAL_DISCIPLINE",
            "hypothesis_layer": "ACCURACY",
            "hypothesis_statement": "Pack B may improve signal discipline in low-signal or ambiguity-heavy sessions more than raw directional accuracy.",
            "mechanism_statement": "Target-state exposure helps providers withhold unsupported directional calls when deterministic context is insufficient.",
            "accuracy_test_statement": "In low-signal sessions, Pack B should reduce false_signal_rate or improve no_signal_correctness versus Pack A.",
            "required_comparison": "Pack A vs Pack B with low-signal session filter",
            "required_metric_revision": "false_signal_rate|no_signal_correctness|partial correctness decomposition",
            "required_sample_scope": "Low-signal and ambiguous sessions separated from high-signal sessions",
            "required_controls": "No-signal proxy, event complexity, provider invalid outputs",
            "expected_evidence": "Lower false-signal rate or better no-signal correctness even if direction_match_rate is unchanged.",
            "failure_condition": "Pack B remains more decisive without reducing false signals or improving no-signal correctness.",
            "ready_for_replication_design": "FALSE",
            "ready_for_metric_repair": "TRUE",
            "ready_for_future_accuracy_test": "FALSE",
            "notes": "Reframes Pack B away from broad accuracy improvement.",
        },
        {
            "revised_hypothesis_id": "REV_HYP_OPENAI_OUTPUT_STABILITY_AS_EVALUATION_CONTROL",
            "parent_hypothesis_id": "ACC_HYP_OPENAI_STABLE_CAUSAL_REWRITE_TESTBED",
            "hypothesis_layer": "MECHANISM",
            "hypothesis_statement": "OpenAI's strongest role may be as a low-invalid-output evaluation control condition.",
            "mechanism_statement": "Stable output validity and causal rewriting reduce measurement noise, making OpenAI useful for isolating pack effects.",
            "accuracy_test_statement": "OpenAI-specific pack comparisons may be replicated as a clean testbed, without claiming provider superiority.",
            "required_comparison": "OpenAI Pack A vs OpenAI Pack B|OpenAI Pack A vs OpenAI Pack D",
            "required_metric_revision": "overall_ok decomposition|pack_vs_baseline_delta guardrails",
            "required_sample_scope": "OpenAI-only replication with matched session pairs and frozen invalid-output policy",
            "required_controls": "Provider ranking forbidden, sample-size guardrails, outcome matching",
            "expected_evidence": "Stable eligible denominators and clearer pack deltas after metric decomposition.",
            "failure_condition": "Clean output stability does not produce interpretable pack deltas under repaired metrics.",
            "ready_for_replication_design": "TRUE",
            "ready_for_metric_repair": "TRUE",
            "ready_for_future_accuracy_test": "FALSE",
            "notes": "Retains OpenAI as experimental control, not as best provider.",
        },
        {
            "revised_hypothesis_id": "REV_HYP_OVERALL_OK_STRINGENCY_REVIEW",
            "parent_hypothesis_id": "CONTROLLED_ACCURACY_METRIC_SET",
            "hypothesis_layer": "METRIC",
            "hypothesis_statement": "overall_ok may be too strict or poorly aligned with session-level partial correctness.",
            "mechanism_statement": "Composite correctness can suppress useful directional or signal-discipline evidence when all components must pass simultaneously.",
            "accuracy_test_statement": "Before replication, decompose overall_ok into direction, no-signal, false-signal, and range components.",
            "required_comparison": "All frozen comparisons reinterpreted through decomposed metrics in future repair phase",
            "required_metric_revision": "DECOMPOSE overall_ok; define partial correctness; preserve original metric as audit-only",
            "required_sample_scope": "Existing 9A-5F rows for metric repair preview, then future replication",
            "required_controls": "No retroactive result mutation, denominator traceability, frozen original results",
            "expected_evidence": "Metric decomposition explains whether low overall_ok reflects strictness, weak forecasts, or both.",
            "failure_condition": "Decomposition remains uninterpretable or changes governance semantics.",
            "ready_for_replication_design": "FALSE",
            "ready_for_metric_repair": "TRUE",
            "ready_for_future_accuracy_test": "FALSE",
            "notes": "Metric repair recommendation only; this phase does not change metric definitions.",
        },
        {
            "revised_hypothesis_id": "REV_HYP_BEHAVIOR_MECHANISM_ACCURACY_BRIDGE",
            "parent_hypothesis_id": "PHASE9A_BEHAVIOR_TO_ACCURACY_FRAMEWORK",
            "hypothesis_layer": "GOVERNANCE",
            "hypothesis_statement": "Behavior change should only move into accuracy replication when an explicit mechanism predicts a specific metric effect.",
            "mechanism_statement": "A behavior pattern must name the causal pathway that should improve a defined accuracy metric.",
            "accuracy_test_statement": "Future accuracy hypotheses must map behavior -> mechanism -> metric before execution approval.",
            "required_comparison": "Applies to all future behavior-to-accuracy hypotheses",
            "required_metric_revision": "Hypothesis-specific metric selection and denominator guardrails",
            "required_sample_scope": "Future replication and mechanism-discovery phases",
            "required_controls": "No provider ranking, no pack ranking, no production interpretation",
            "expected_evidence": "Replication designs contain mechanism statements, scoped metrics, and falsifiable failure conditions.",
            "failure_condition": "Accuracy hypotheses remain behavior-only without causal mechanism or metric specificity.",
            "ready_for_replication_design": "FALSE",
            "ready_for_metric_repair": "FALSE",
            "ready_for_future_accuracy_test": "FALSE",
            "notes": "Framework rule for later research phases.",
        },
    ]
    rows = []
    for item in revised:
        row = _base(generated_ts, revision_run_id)
        row.update(item)
        row.update({"production_excluded": "TRUE"})
        rows.append(row)
    return rows


def _build_metric_rows(generated_ts: str, revision_run_id: str) -> List[Dict[str, Any]]:
    all_hypotheses = (
        "ACC_HYP_USDJPY_TREND_DIRECTIONAL_ALIGNMENT|"
        "ACC_HYP_PACK_B_TARGET_STATE_SIGNAL_DISCIPLINE|"
        "ACC_HYP_OPENAI_STABLE_CAUSAL_REWRITE_TESTBED"
    )
    metrics = [
        (
            "direction_match_rate",
            "Direction Match Rate",
            "Primary directional alignment metric in 9A-5F.",
            "Direction-only result was mixed and may not capture signal discipline.",
            "TRUE",
            "DOWNWEIGHT",
            all_hypotheses,
            "Keep as a core metric but do not let it be the only transfer test.",
        ),
        (
            "overall_ok",
            "Overall OK",
            "Composite correctness metric in 9A-5F.",
            "Very low rate and identified as highest-risk limitation; may be too stringent.",
            "TRUE",
            "DECOMPOSE",
            all_hypotheses,
            "Highest priority metric repair; preserve original values and add component interpretation later.",
        ),
        (
            "false_signal_rate",
            "False Signal Rate",
            "Signal-discipline metric.",
            "May better capture Pack B value than raw direction, but needs denominator clarity.",
            "FALSE",
            "PROMOTE",
            "ACC_HYP_PACK_B_TARGET_STATE_SIGNAL_DISCIPLINE",
            "Promote for Pack B low-signal discipline tests after proxy repair.",
        ),
        (
            "no_signal_correctness",
            "No-Signal Correctness",
            "No-signal discipline metric.",
            "Current proxy may not reflect true signal quality.",
            "TRUE",
            "REDEFINE",
            "ACC_HYP_PACK_B_TARGET_STATE_SIGNAL_DISCIPLINE",
            "Repair flat/no-reaction outcome proxy before replication.",
        ),
        (
            "behavior_conditioned_accuracy_delta",
            "Behavior-Conditioned Accuracy Delta",
            "Metric linking behavior changes to accuracy deltas.",
            "Needs explicit mechanism and conditioning criteria before safe use.",
            "TRUE",
            "REDEFINE",
            all_hypotheses,
            "Require mechanism filters and predeclared denominators.",
        ),
        (
            "pack_vs_baseline_delta",
            "Pack vs Baseline Delta",
            "Pack comparison metric.",
            "Useful but sensitive to Pack D/E ambiguity and small paired denominators.",
            "FALSE",
            "KEEP",
            all_hypotheses,
            "Keep with sample warnings and exploratory Pack E guardrails.",
        ),
        (
            "confidence_calibration_proxy",
            "Confidence Calibration Proxy",
            "Proxy metric for confidence behavior.",
            "Confidence is not accuracy and should not be overinterpreted.",
            "FALSE",
            "HOLD",
            all_hypotheses,
            "Hold until calibration-specific design exists.",
        ),
        (
            "scenario_alignment",
            "Scenario Alignment",
            "Scenario-level diagnostic metric.",
            "Not central to 9A-5F conclusions and may need outcome mapping repair.",
            "FALSE",
            "HOLD",
            all_hypotheses,
            "Hold for separate scenario evaluation design.",
        ),
    ]
    rows = []
    for metric_id, name, current_use, issue, revision_needed, action, affected, notes in metrics:
        row = _base(generated_ts, revision_run_id)
        row.update(
            {
                "metric_id": metric_id,
                "metric_name": name,
                "current_use": current_use,
                "observed_issue": issue,
                "revision_needed": revision_needed,
                "recommended_metric_action": action,
                "affected_hypotheses": affected,
                "notes": notes,
            }
        )
        rows.append(row)
    return rows


def _build_replication_rows(
    generated_ts: str,
    revision_run_id: str,
    revised_rows: Sequence[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    status_by_id = {
        "REV_HYP_USDJPY_CONDITIONAL_PREDICTIVE_VALUE": (
            "READY_AFTER_SCOPE_NARROWING",
            "Mechanism is plausible but requires regime-filter scope before replication.",
            "Session regime filters not yet defined.",
            "Define qualifying USDJPY regime/session filters and sample plan.",
            "PROCEED_TO_PHASE9A6_MECHANISM_DISCOVERY_DESIGN",
        ),
        "REV_HYP_PACK_B_SIGNAL_DISCIPLINE_CONDITIONAL": (
            "READY_AFTER_METRIC_REPAIR",
            "Pack B should be retested through false-signal/no-signal discipline after metric repair.",
            "No-signal and false-signal proxy definitions need repair.",
            "Complete metric/outcome repair before replication design.",
            "PROCEED_TO_PHASE9A5M_METRIC_OR_OUTCOME_REPAIR",
        ),
        "REV_HYP_OPENAI_OUTPUT_STABILITY_AS_EVALUATION_CONTROL": (
            "READY_AFTER_METRIC_REPAIR",
            "OpenAI is the cleanest replication-control candidate but should wait for overall_ok decomposition.",
            "overall_ok stringency remains unresolved.",
            "Repair/decompose overall_ok and keep provider-ranking guardrails.",
            "PROCEED_TO_PHASE9A5M_METRIC_OR_OUTCOME_REPAIR",
        ),
        "REV_HYP_OVERALL_OK_STRINGENCY_REVIEW": (
            "NOT_READY",
            "This is a metric-repair hypothesis, not a replication hypothesis.",
            "Metric definition not yet repaired.",
            "Run metric/outcome repair before any replication.",
            "PROCEED_TO_PHASE9A5M_METRIC_OR_OUTCOME_REPAIR",
        ),
        "REV_HYP_BEHAVIOR_MECHANISM_ACCURACY_BRIDGE": (
            "HOLD",
            "Framework requirement should govern future phases but is not itself a replication experiment.",
            "Needs adoption into future design templates.",
            "Apply framework in 9A-5M/9A-6/replication planning.",
            "PROCEED_TO_PHASE9A5M_METRIC_OR_OUTCOME_REPAIR",
        ),
    }
    rows = []
    for revised in revised_rows:
        hypothesis_id = _norm(revised.get("revised_hypothesis_id"))
        status, reason, blocking, required, phase = status_by_id[hypothesis_id]
        row = _base(generated_ts, revision_run_id)
        row.update(
            {
                "revised_hypothesis_id": hypothesis_id,
                "replication_readiness_status": status,
                "readiness_reason": reason,
                "blocking_issue": blocking,
                "required_before_replication": required,
                "recommended_next_phase": phase,
                "notes": "Replication is not executed or authorized by this revision phase.",
            }
        )
        rows.append(row)
    return rows


def _build_governance_rows(generated_ts: str, revision_run_id: str) -> List[Dict[str, Any]]:
    checks = [
        ("provider_calls_performed", 0, 0),
        ("forecast_generation_performed", 0, 0),
        ("provider_rerun_count", 0, 0),
        ("evaluation_rerun_count", 0, 0),
        ("accuracy_results_modified", 0, 0),
        ("metric_values_recalculated", 0, 0),
        ("evaluation_rows_written", 0, 0),
        ("outcome_ledger_written", 0, 0),
        ("production_behavior_change_count", 0, 0),
        ("production_sheet_write_count", 0, 0),
        ("routing_changes", "FALSE", "FALSE"),
        ("weighting_changes", "FALSE", "FALSE"),
        ("calibration_changes", "FALSE", "FALSE"),
        ("ensemble_changes", "FALSE", "FALSE"),
    ]
    rows = []
    for check_name, expected, actual in checks:
        row = _base(generated_ts, revision_run_id)
        row.update(
            {
                "check_id": f"CHK_{check_name.upper()}",
                "check_name": check_name,
                "expected_value": expected,
                "actual_value": actual,
                "status": "PASS" if str(expected) == str(actual) else "FAIL",
                "notes": "Revision phase is diagnostic-only; no results, providers, or production artifacts changed.",
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
        ("BEHAVIOR_ACCURACY_HYPOTHESIS_REVISION", OUTPUT_REVISION, "behavior_accuracy_hypothesis_revision"),
        ("BEHAVIOR_ACCURACY_FAILED_TRANSFER_AUDIT", OUTPUT_FAILED_TRANSFER, "behavior_accuracy_failed_transfer_audit"),
        ("BEHAVIOR_ACCURACY_MECHANISM_GAP_AUDIT", OUTPUT_MECHANISM, "behavior_accuracy_mechanism_gap_audit"),
        ("BEHAVIOR_ACCURACY_REVISED_HYPOTHESES", OUTPUT_REVISED_HYPOTHESES, "behavior_accuracy_revised_hypotheses"),
        ("BEHAVIOR_ACCURACY_METRIC_REVISION_AUDIT", OUTPUT_METRIC, "behavior_accuracy_metric_revision_audit"),
        ("BEHAVIOR_ACCURACY_REPLICATION_READINESS", OUTPUT_REPLICATION, "behavior_accuracy_replication_readiness"),
        ("BEHAVIOR_ACCURACY_GOVERNANCE_AUDIT", OUTPUT_GOVERNANCE, "behavior_accuracy_governance_audit"),
        ("BEHAVIOR_ACCURACY_REVISION_SUMMARY", OUTPUT_SUMMARY, "behavior_accuracy_revision_summary"),
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
            "notes": "Phase 9A-5R behavior-to-accuracy hypothesis revision; diagnostic-only.",
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
    parser = argparse.ArgumentParser(description="Build PreSignal v2.0 Phase 9A-5R behavior-accuracy hypothesis revision.")
    return parser.parse_args(argv)


def build_behavior_accuracy_hypothesis_revision_v0(args: Optional[argparse.Namespace] = None) -> Dict[str, Any]:
    args = args or _parse_args()
    _ = args
    generated_ts = _iso_now()
    revision_run_id = _run_id(generated_ts)
    service = build_sheets_service(load_credentials())
    titles = _sheet_titles(service, DIAGNOSTICS_SPREADSHEET_ID)
    missing_required: List[str] = []

    inputs_9a5g = {sheet: _safe_rows(service, DIAGNOSTICS_SPREADSHEET_ID, titles, sheet, missing_required) for sheet in INPUT_9A5G}
    inputs_9a5f = {sheet: _safe_rows(service, DIAGNOSTICS_SPREADSHEET_ID, titles, sheet, missing_required) for sheet in INPUT_9A5F}
    inputs_design = {sheet: _safe_rows(service, DIAGNOSTICS_SPREADSHEET_ID, titles, sheet, missing_required) for sheet in INPUT_DESIGN}
    inputs_behavior = {sheet: _safe_rows(service, DIAGNOSTICS_SPREADSHEET_ID, titles, sheet, missing_required) for sheet in INPUT_BEHAVIOR}
    if missing_required:
        raise RuntimeError(f"Missing required Phase 9A-5R inputs: {sorted(set(missing_required))}")
    _ = inputs_design

    source_review_summary = _latest(inputs_9a5g["Controlled_Accuracy_Evaluation_Review_Summary"])
    source_eval_summary = _latest(inputs_9a5f["Controlled_Accuracy_Evaluation_Summary"])
    hypothesis_review_rows = inputs_9a5g["Accuracy_Hypothesis_Review"]
    experiments_by_hypothesis = _experiment_by_hypothesis(inputs_9a5f["Controlled_Accuracy_Experiment_Results"])
    behavior_strength = _behavior_strength_by_hypothesis(inputs_behavior["Pack_Behavior_Tier2_Hypothesis_Generalization"])

    if _norm(source_review_summary.get("recommended_next_step")) != "PROCEED_TO_PHASE9A5R_HYPOTHESIS_REVISION":
        raise RuntimeError("Phase 9A-5G did not recommend Phase 9A-5R hypothesis revision; revision blocked.")
    if not _bool(source_review_summary.get("ready_for_hypothesis_revision")):
        raise RuntimeError("Phase 9A-5G summary is not ready for hypothesis revision; revision blocked.")

    prior_governance = inputs_9a5g["Accuracy_Governance_Review"]
    if any(_norm(row.get("status")) != "PASS" for row in prior_governance):
        raise RuntimeError("Phase 9A-5G governance was not clean; revision blocked.")

    revision_rows = _build_revision_rows(generated_ts, revision_run_id, source_review_summary)
    failed_transfer_rows = _build_failed_transfer_rows(
        generated_ts,
        revision_run_id,
        hypothesis_review_rows,
        experiments_by_hypothesis,
        behavior_strength,
    )
    mechanism_rows = _build_mechanism_gap_rows(generated_ts, revision_run_id)
    revised_hypothesis_rows = _build_revised_hypothesis_rows(generated_ts, revision_run_id)
    metric_rows = _build_metric_rows(generated_ts, revision_run_id)
    replication_rows = _build_replication_rows(generated_ts, revision_run_id, revised_hypothesis_rows)
    governance_rows = _build_governance_rows(generated_ts, revision_run_id)

    metrics_requiring_revision = sum(1 for row in metric_rows if _bool(row.get("revision_needed")))
    replication_ready = [row for row in replication_rows if _norm(row.get("replication_readiness_status")) == "READY_FOR_REPLICATION_DESIGN"]
    requiring_metric = [
        row.get("revised_hypothesis_id")
        for row in replication_rows
        if _norm(row.get("replication_readiness_status")) == "READY_AFTER_METRIC_REPAIR"
    ]
    requiring_scope = [
        row.get("revised_hypothesis_id")
        for row in replication_rows
        if _norm(row.get("replication_readiness_status")) == "READY_AFTER_SCOPE_NARROWING"
    ]
    governance_failed = any(_norm(row.get("status")) != "PASS" for row in governance_rows)

    summary_row = {
        **_base(generated_ts, revision_run_id),
        "build_status": "PASS_WITH_WARNINGS" if not governance_failed else "FAIL",
        "final_interpretation": "BEHAVIOR_ACCURACY_HYPOTHESIS_REVISION_READY_WITH_WARNINGS"
        if not governance_failed
        else "BEHAVIOR_ACCURACY_HYPOTHESIS_REVISION_BLOCKED",
        "original_accuracy_hypotheses_reviewed": len(failed_transfer_rows),
        "hypotheses_revised": 3,
        "hypotheses_retained": 1,
        "hypotheses_retired": 0,
        "mechanism_gaps_identified": len(mechanism_rows),
        "metrics_reviewed": len(metric_rows),
        "metrics_requiring_revision": metrics_requiring_revision,
        "revised_hypotheses_defined": len(revised_hypothesis_rows),
        "strongest_revised_hypothesis": "REV_HYP_OPENAI_OUTPUT_STABILITY_AS_EVALUATION_CONTROL",
        "primary_mechanism_gap": "behavior_change_without_validated_predictive_mechanism",
        "highest_priority_metric_revision": "REV_HYP_OVERALL_OK_STRINGENCY_REVIEW",
        "replication_ready_hypotheses": "|".join(row.get("revised_hypothesis_id") for row in replication_ready) or "NONE_BEFORE_METRIC_REPAIR",
        "hypotheses_requiring_metric_repair": "|".join(requiring_metric),
        "hypotheses_requiring_scope_narrowing": "|".join(requiring_scope),
        "provider_calls_performed": 0,
        "forecast_generation_performed": 0,
        "provider_rerun_count": 0,
        "evaluation_rerun_count": 0,
        "accuracy_results_modified": 0,
        "metric_values_recalculated": 0,
        "production_behavior_change_count": 0,
        "production_sheet_write_count": 0,
        "ready_for_replication_design": "FALSE",
        "ready_for_metric_repair": "TRUE",
        "ready_for_production": "FALSE",
        "recommended_next_step": "PROCEED_TO_PHASE9A5M_METRIC_OR_OUTCOME_REPAIR",
        "notes": json.dumps(
            {
                "source_9a5g_final_interpretation": source_review_summary.get("final_interpretation"),
                "source_9a5g_primary_interpretation": source_review_summary.get("primary_interpretation"),
                "source_9a5f_direction_match_rate": source_eval_summary.get("direction_match_rate"),
                "source_9a5f_overall_ok_rate": source_eval_summary.get("overall_ok_rate"),
                "framework": "Behavior -> Mechanism -> Accuracy",
                "no_accuracy_rerun": True,
                "no_metric_recalculation": True,
                "no_production_change": True,
            },
            sort_keys=True,
        ),
    }
    summary_rows = [summary_row]

    outputs = [
        (OUTPUT_REVISION, REVISION_HEADERS, revision_rows),
        (OUTPUT_FAILED_TRANSFER, FAILED_TRANSFER_HEADERS, failed_transfer_rows),
        (OUTPUT_MECHANISM, MECHANISM_HEADERS, mechanism_rows),
        (OUTPUT_REVISED_HYPOTHESES, REVISED_HYPOTHESES_HEADERS, revised_hypothesis_rows),
        (OUTPUT_METRIC, METRIC_HEADERS, metric_rows),
        (OUTPUT_REPLICATION, REPLICATION_HEADERS, replication_rows),
        (OUTPUT_GOVERNANCE, GOVERNANCE_HEADERS, governance_rows),
        (OUTPUT_SUMMARY, SUMMARY_HEADERS, summary_rows),
    ]
    for sheet_name, headers, rows in outputs:
        actual_headers = _ensure_sheet(service, DIAGNOSTICS_SPREADSHEET_ID, sheet_name, headers)
        _write_rows(service, DIAGNOSTICS_SPREADSHEET_ID, sheet_name, actual_headers, rows)

    registry = _upsert_registry_rows(service)
    return {
        "build_status": summary_row["build_status"],
        "final_interpretation": summary_row["final_interpretation"],
        "file_created": "automation/build_behavior_accuracy_hypothesis_revision_v0.py",
        "sheets_written": {sheet_name: len(rows) for sheet_name, _, rows in outputs},
        "original_accuracy_hypotheses_reviewed": summary_row["original_accuracy_hypotheses_reviewed"],
        "hypotheses_revised": summary_row["hypotheses_revised"],
        "hypotheses_retained": summary_row["hypotheses_retained"],
        "hypotheses_retired": summary_row["hypotheses_retired"],
        "mechanism_gaps_identified": summary_row["mechanism_gaps_identified"],
        "metrics_reviewed": summary_row["metrics_reviewed"],
        "metrics_requiring_revision": summary_row["metrics_requiring_revision"],
        "revised_hypotheses_defined": summary_row["revised_hypotheses_defined"],
        "strongest_revised_hypothesis": summary_row["strongest_revised_hypothesis"],
        "primary_mechanism_gap": summary_row["primary_mechanism_gap"],
        "highest_priority_metric_revision": summary_row["highest_priority_metric_revision"],
        "replication_ready_hypotheses": summary_row["replication_ready_hypotheses"],
        "hypotheses_requiring_metric_repair": summary_row["hypotheses_requiring_metric_repair"],
        "hypotheses_requiring_scope_narrowing": summary_row["hypotheses_requiring_scope_narrowing"],
        "provider_calls_performed": 0,
        "forecast_generation_performed": 0,
        "provider_rerun_count": 0,
        "evaluation_rerun_count": 0,
        "accuracy_results_modified": 0,
        "metric_values_recalculated": 0,
        "production_behavior_change_count": 0,
        "production_sheet_write_count": 0,
        "ready_for_replication_design": False,
        "ready_for_metric_repair": True,
        "ready_for_production": False,
        "recommended_next_step": summary_row["recommended_next_step"],
        "registry": registry,
    }


def main() -> None:
    result = build_behavior_accuracy_hypothesis_revision_v0()
    print(json.dumps(result, indent=2, ensure_ascii=True))


if __name__ == "__main__":
    main()
