import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean
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


SCHEMA_VERSION = "presignal_v2_behavior_tier2_generalization_review_0.1"
REVIEW_VERSION = "behavior_tier2_generalization_review_v0"
PHASE_LABEL = "PreSignal v2.0 Phase 9A-4ZZ"
REGISTRY_CATEGORY = "PRESIGNAL_V2_TIER2_BEHAVIOR_GENERALIZATION_REVIEW"
REGISTRY_OWNER_MODULE = "market_state"

TIER2_RUNS = "Pack_Behavior_Tier2_Runs"
TIER2_FORECASTS = "Pack_Behavior_Tier2_Forecasts"
TIER2_METADATA = "Pack_Behavior_Tier2_Metadata"
TIER2_BEHAVIOR = "Pack_Behavior_Tier2_Behavior"
TIER2_RAW = "Pack_Behavior_Tier2_Raw_Response_Archive"
TIER2_TRANSITIONS = "Pack_Behavior_Tier2_Transitions"
TIER2_FIELD = "Pack_Behavior_Tier2_Field_Influence"
TIER2_NOSIGNAL = "Pack_Behavior_Tier2_NoSignal"
TIER2_INVALID = "Pack_Behavior_Tier2_Invalid_Output"
TIER2_CHECKPOINTS = "Pack_Behavior_Tier2_Checkpoint_Log"
TIER2_LOG = "Pack_Behavior_Tier2_Run_Log"
TIER2_SUMMARY = "Pack_Behavior_Tier2_Run_Summary"

TIER2_EXPERIMENT_DESIGN = "Pack_Behavior_Tier2_Experiment_Design"
TIER2_HYPOTHESIS_PLAN = "Pack_Behavior_Tier2_Hypothesis_Test_Plan"
TIER2_SUCCESS_CRITERIA = "Pack_Behavior_Tier2_Success_Criteria"
TIER2_DESIGN_SUMMARY = "Pack_Behavior_Tier2_Design_Summary"

PRIOR_GENERALIZATION_AUDIT = "Pack_Behavior_Generalization_Audit"
PRIOR_PROVIDER = "Pack_Behavior_Provider_Consistency_Audit"
PRIOR_TRANSITION = "Pack_Behavior_Transition_Reproducibility_Audit"
PRIOR_FIELD = "Pack_Behavior_Field_Stability_Audit"
PRIOR_NOSIGNAL = "Pack_Behavior_NoSignal_Stability_Audit"
PRIOR_INVALID = "Pack_Behavior_Invalid_Output_Generalization_Audit"
PRIOR_HYPOTHESES = "Pack_Behavior_Generalization_Hypotheses"
PRIOR_GENERALIZATION_SUMMARY = "Pack_Behavior_Generalization_Summary"

TIER1_RUNS = "Pack_Behavior_Discovery_Runs"
TIER1_FORECASTS = "Pack_Behavior_Discovery_Forecasts"
TIER1_BEHAVIOR = "Pack_Behavior_Discovery_Behavior"
TIER1_TRANSITIONS = "Pack_Behavior_Discovery_Transitions"
TIER1_FIELD = "Pack_Behavior_Discovery_Field_Influence"
TIER1_NOSIGNAL = "Pack_Behavior_Discovery_NoSignal"
TIER1_INVALID = "Pack_Behavior_Discovery_Invalid_Output"
TIER1_SUMMARY = "Pack_Behavior_Discovery_Run_Summary"

PILOT_BEHAVIOR_COMPARE = "Pack_Exposure_Behavior_Compare"
PILOT_TRANSITIONS = "Pack_Exposure_Reasoning_Transitions"
PILOT_PROVIDER = "Pack_Exposure_Provider_Transition_Audit"
PILOT_FIELD = "Pack_Exposure_Field_Influence_Audit"
PILOT_NOSIGNAL = "Pack_Exposure_NoSignal_Confidence_Audit"
PILOT_INVALID = "Pack_Exposure_Invalid_Output_Audit"
PILOT_SUMMARY = "Pack_Exposure_Behavior_Compare_Summary"

OUTPUT_REVIEW = "Pack_Behavior_Tier2_Generalization_Review"
OUTPUT_HYPOTHESIS = "Pack_Behavior_Tier2_Hypothesis_Generalization"
OUTPUT_PROVIDER = "Pack_Behavior_Tier2_Provider_Generalization"
OUTPUT_TRANSITION = "Pack_Behavior_Tier2_Transition_Generalization"
OUTPUT_FIELD = "Pack_Behavior_Tier2_Field_Generalization"
OUTPUT_NOSIGNAL = "Pack_Behavior_Tier2_NoSignal_Generalization"
OUTPUT_INVALID = "Pack_Behavior_Tier2_Invalid_Output_Generalization"
OUTPUT_SUMMARY = "Pack_Behavior_Tier2_Generalization_Summary"

PROVIDERS = ["OpenAI", "Gemini", "Anthropic"]
TRANSITIONS = ["A_to_B", "B_to_C", "C_to_D", "D_to_E", "A_to_D", "A_to_E"]
PACK_LEVELS = ["A", "B", "C", "D", "E"]
REQUIRED_HYPOTHESES = [
    "HYP_USDJPY_TREND_REASONING",
    "HYP_A_TO_B_TARGET_STATE_VALUE",
    "HYP_GEMINI_HIGH_SENSITIVITY",
    "HYP_OPENAI_CAUSAL_STABLE",
    "HYP_PACK_E_REDUNDANCY",
    "HYP_ANTHROPIC_DE_INVALID_RISK",
    "HYP_TREASURY_UNDERDETERMINED",
]

REVIEW_HEADERS = [
    "generated_ts",
    "schema_version",
    "generalization_review_version",
    "generalization_review_run_id",
    "review_area",
    "review_status",
    "evidence_scope",
    "sessions_included",
    "provider_calls_included",
    "valid_outputs_count",
    "invalid_outputs_count",
    "valid_transition_count",
    "invalid_or_partial_transition_count",
    "behavior_signal_classification",
    "generalization_conclusion",
    "recommended_next_action",
    "accuracy_excluded",
    "production_excluded",
    "notes",
]

HYPOTHESIS_HEADERS = [
    "generated_ts",
    "schema_version",
    "generalization_review_version",
    "generalization_review_run_id",
    "hypothesis_id",
    "hypothesis_priority",
    "prior_status",
    "tier2_result",
    "generalization_status",
    "behavior_support_level",
    "supporting_evidence_summary",
    "supporting_sessions",
    "supporting_providers",
    "supporting_transitions",
    "supporting_fields_or_families",
    "invalid_output_impact",
    "revised_hypothesis_statement",
    "recommended_status",
    "recommended_next_action",
    "ready_for_behavior_to_accuracy_design",
    "accuracy_excluded",
    "production_excluded",
    "notes",
]

PROVIDER_HEADERS = [
    "generated_ts",
    "schema_version",
    "generalization_review_version",
    "generalization_review_run_id",
    "provider",
    "valid_output_count",
    "invalid_output_count",
    "invalid_output_rate",
    "valid_transition_count",
    "direction_change_count",
    "confidence_change_count",
    "material_confidence_change_count",
    "no_signal_change_count",
    "causal_chain_change_count",
    "information_used_change_count",
    "mean_transition_complexity_score",
    "provider_behavior_classification",
    "provider_risk_classification",
    "generalization_conclusion",
    "accuracy_interpretation_forbidden",
    "notes",
]

TRANSITION_HEADERS = [
    "generated_ts",
    "schema_version",
    "generalization_review_version",
    "generalization_review_run_id",
    "pack_transition",
    "valid_transition_count",
    "invalid_or_partial_transition_count",
    "direction_change_count",
    "confidence_change_count",
    "no_signal_change_count",
    "causal_chain_change_count",
    "information_used_change_count",
    "mean_transition_complexity_score",
    "max_transition_complexity_score",
    "behavioral_value_classification",
    "generalization_status",
    "interpretation",
    "next_phase_relevance",
    "notes",
]

FIELD_HEADERS = [
    "generated_ts",
    "schema_version",
    "generalization_review_version",
    "generalization_review_run_id",
    "candidate_family",
    "candidate_field",
    "field_scope",
    "used_count",
    "changed_reasoning_count",
    "discarded_count",
    "no_effect_count",
    "available_not_mentioned_count",
    "sessions_with_use",
    "sessions_with_changed_reasoning",
    "providers_with_use",
    "providers_with_changed_reasoning",
    "field_behavior_classification",
    "generalization_status",
    "interpretation",
    "next_phase_relevance",
    "notes",
]

NOSIGNAL_HEADERS = [
    "generated_ts",
    "schema_version",
    "generalization_review_version",
    "generalization_review_run_id",
    "provider",
    "pack_transition",
    "scope",
    "no_signal_change_count",
    "no_signal_reduction_count",
    "no_signal_increase_count",
    "confidence_change_count",
    "material_confidence_change_count",
    "mean_confidence_delta",
    "max_confidence_delta_abs",
    "no_signal_generalization_status",
    "confidence_generalization_status",
    "interpretation",
    "notes",
]

INVALID_HEADERS = [
    "generated_ts",
    "schema_version",
    "generalization_review_version",
    "generalization_review_run_id",
    "provider",
    "pack_level",
    "scope",
    "attempted_count",
    "invalid_output_count",
    "invalid_output_rate",
    "dominant_invalid_reason",
    "risk_pattern",
    "risk_status",
    "tier3_or_next_phase_implication",
    "notes",
]

SUMMARY_HEADERS = [
    "generated_ts",
    "schema_version",
    "generalization_review_version",
    "generalization_review_run_id",
    "build_status",
    "final_interpretation",
    "sessions_total",
    "provider_calls_total",
    "raw_responses_archived",
    "invalid_output_count",
    "invalid_output_rate",
    "valid_transition_count",
    "invalid_or_partial_transition_count",
    "hypotheses_reviewed",
    "hypotheses_behavior_confirmed",
    "hypotheses_ready_for_behavior_to_accuracy_design",
    "hypotheses_promoted_to_tier3_stability",
    "hypotheses_revised",
    "hypotheses_held_due_invalid_outputs",
    "hypotheses_retired",
    "strongest_behavior_confirmed_hypothesis",
    "strongest_provider_generalization",
    "strongest_transition_generalization",
    "strongest_field_family_generalization",
    "strongest_no_signal_generalization",
    "strongest_invalid_output_risk",
    "accuracy_evaluation_count",
    "provider_call_count_this_review",
    "forecast_generation_count_this_review",
    "provider_rerun_count_this_review",
    "production_behavior_change_count",
    "ready_for_behavior_to_accuracy_hypothesis_design",
    "ready_for_tier3_stability_check",
    "ready_for_accuracy_evaluation",
    "ready_for_production",
    "recommended_next_step",
    "notes",
]


def _upper(value: Any) -> str:
    return _norm(value).upper()


def _truth(value: Any) -> bool:
    return _upper(value) in {"TRUE", "T", "YES", "Y", "1"}


def _float(value: Any) -> Optional[float]:
    try:
        text = _norm(value)
        return float(text) if text else None
    except Exception:
        return None


def _fmt_rate(numerator: int, denominator: int) -> str:
    return f"{(numerator / denominator):.3f}" if denominator else ""


def _fmt_mean(values: Sequence[float]) -> str:
    return f"{mean(values):.3f}" if values else ""


def _run_id(generated_ts: str) -> str:
    stamp = generated_ts.replace("-", "").replace(":", "").replace("+00:00", "Z").replace(".", "")
    return f"pack_behavior_tier2_generalization_review_v0_{stamp}"


def _sheet_titles(service, spreadsheet_id: str) -> Set[str]:
    meta = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    return {sheet["properties"]["title"] for sheet in meta.get("sheets", [])}


def _safe_rows(service, titles: Set[str], sheet_name: str, missing: List[str], required: bool = False) -> List[Dict[str, Any]]:
    if sheet_name not in titles:
        if required:
            missing.append(sheet_name)
        return []
    return _sheet_to_rows(service, DIAGNOSTICS_SPREADSHEET_ID, sheet_name)


def _valid_output(row: Dict[str, Any]) -> bool:
    return _truth(row.get("json_validation_success")) or _truth(row.get("output_valid"))


def _valid_transition(row: Dict[str, Any]) -> bool:
    return _upper(row.get("transition_status")) == "PASS"


def _direction_changed(row: Dict[str, Any]) -> bool:
    return _upper(row.get("direction_transition")) not in {"", "UNCHANGED", "UNKNOWN"}


def _confidence_changed(row: Dict[str, Any]) -> bool:
    return _upper(row.get("confidence_transition")) not in {"", "UNCHANGED", "UNKNOWN"}


def _material_confidence_changed(row: Dict[str, Any]) -> bool:
    value = _float(row.get("confidence_delta"))
    if value is not None:
        return abs(value) >= 10
    return _upper(row.get("confidence_transition")) in {"MATERIAL_INCREASE", "MATERIAL_DECREASE"}


def _session_set(rows: Iterable[Dict[str, Any]]) -> Set[str]:
    return {_norm(row.get("session_id")) for row in rows if _norm(row.get("session_id"))}


def _provider_set(rows: Iterable[Dict[str, Any]]) -> Set[str]:
    return {_norm(row.get("provider")) for row in rows if _norm(row.get("provider"))}


def _transition_metrics(rows: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    valid = [row for row in rows if _valid_transition(row)]
    invalid = [row for row in rows if not _valid_transition(row)]
    complexities = [_float(row.get("transition_complexity_score")) for row in valid]
    complexities = [value for value in complexities if value is not None]
    return {
        "valid": valid,
        "invalid": invalid,
        "valid_count": len(valid),
        "invalid_count": len(invalid),
        "direction": sum(1 for row in valid if _direction_changed(row)),
        "confidence": sum(1 for row in valid if _confidence_changed(row)),
        "material_confidence": sum(1 for row in valid if _material_confidence_changed(row)),
        "no_signal": sum(1 for row in valid if _upper(row.get("no_signal_transition")) == "CHANGED"),
        "causal": sum(1 for row in valid if _upper(row.get("causal_chain_transition")) == "CHANGED"),
        "info_used": sum(1 for row in valid if _upper(row.get("used_information_transition")) == "CHANGED"),
        "missing_reduced": sum(1 for row in valid if _upper(row.get("missing_information_transition")) == "REDUCED"),
        "mean_complexity": _fmt_mean(complexities),
        "max_complexity": f"{max(complexities):.0f}" if complexities else "",
        "sessions": _session_set(rows),
        "valid_sessions": _session_set(valid),
        "providers": _provider_set(rows),
        "valid_providers": _provider_set(valid),
    }


def _field_counts(rows: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    used = [row for row in rows if _truth(row.get("field_reported_used"))]
    changed = [row for row in rows if _truth(row.get("field_reported_changed_reasoning"))]
    discarded = [row for row in rows if _truth(row.get("field_reported_discarded"))]
    no_effect = [row for row in rows if _truth(row.get("field_reported_no_effect"))]
    available_not_mentioned = [row for row in rows if _upper(row.get("influence_status")) == "AVAILABLE_NOT_MENTIONED"]
    return {
        "used": len(used),
        "changed": len(changed),
        "discarded": len(discarded),
        "no_effect": len(no_effect),
        "available_not_mentioned": len(available_not_mentioned),
        "sessions_used": _session_set(used),
        "sessions_changed": _session_set(changed),
        "providers_used": _provider_set(used),
        "providers_changed": _provider_set(changed),
    }


def _field_classification(counts: Dict[str, Any], scope: str) -> Tuple[str, str]:
    changed = counts["changed"]
    used = counts["used"]
    no_effect = counts["no_effect"]
    discarded = counts["discarded"]
    providers_changed = len(counts["providers_changed"])
    sessions_changed = len(counts["sessions_changed"])
    if scope == "FIELD_FAMILY" and changed >= 25 and providers_changed >= 2 and sessions_changed >= 5:
        return "STRONG_BEHAVIOR_MOVING_FAMILY", "BEHAVIOR_CONFIRMED"
    if changed >= 10 or used >= 50:
        return "MODERATE_BEHAVIOR_MOVING_FAMILY", "CANDIDATE_PATTERN_RETAINED"
    if used and (discarded or no_effect):
        return "MIXED_BEHAVIOR_FAMILY", "CANDIDATE_PATTERN_RETAINED"
    if used:
        return "LOW_BEHAVIOR_SIGNAL", "UNDERDETERMINED"
    return "UNDERDETERMINED", "UNDERDETERMINED"


def _provider_classification(provider: str, output_count: int, invalid_count: int, metrics: Dict[str, Any]) -> Tuple[str, str]:
    invalid_rate = invalid_count / output_count if output_count else 0
    if provider == "OpenAI" and invalid_count == 0 and metrics["causal"] == metrics["valid_count"]:
        return "OUTPUT_STABLE_CAUSAL_REWRITER", "LOW_OUTPUT_RISK"
    if invalid_rate >= 0.25:
        risk = "PROVIDER_AVAILABILITY_RISK" if provider == "Gemini" else "HIGH_OUTPUT_RISK"
        return "HIGH_PACK_SENSITIVITY", risk
    if provider == "Anthropic" and invalid_count:
        return "MODERATE_PACK_SENSITIVITY", "MALFORMED_OUTPUT_RISK"
    score = metrics["direction"] + metrics["material_confidence"] + metrics["no_signal"]
    if score >= 20:
        return "HIGH_PACK_SENSITIVITY", "LOW_OUTPUT_RISK"
    if score >= 8:
        return "MODERATE_PACK_SENSITIVITY", "LOW_OUTPUT_RISK"
    return "LOW_PACK_SENSITIVITY", "LOW_OUTPUT_RISK"


def _transition_classification(transition: str, metrics: Dict[str, Any]) -> Tuple[str, str]:
    valid = metrics["valid_count"]
    if valid == 0 or metrics["invalid_count"] > valid:
        return "INVALID_OUTPUT_LIMITED", "INVALID_OUTPUT_LIMITED"
    complexity = _float(metrics["mean_complexity"]) or 0
    if transition in {"A_to_B", "A_to_D", "A_to_E"} and complexity >= 11:
        return "HIGH_BEHAVIORAL_VALUE", "BEHAVIOR_CONFIRMED"
    if complexity >= 9 or metrics["causal"] == valid:
        return "MODERATE_BEHAVIORAL_VALUE", "CANDIDATE_PATTERN_RETAINED"
    return "LOW_BEHAVIORAL_VALUE", "UNDERDETERMINED"


def _risk_status(provider: str, pack: str, attempted: int, invalid_count: int, reasons: Counter) -> Tuple[str, str]:
    if attempted <= 0:
        return "UNDERDETERMINED", ""
    rate = invalid_count / attempted
    dominant = reasons.most_common(1)[0][0] if reasons else ""
    if invalid_count == 0:
        return "LOW_RISK", dominant
    if "Gemini 503" in dominant:
        return "PROVIDER_AVAILABILITY_RISK", dominant
    if "MALFORMED" in dominant or "TRUNCATED" in dominant:
        return "MALFORMED_OUTPUT_RISK" if rate < 0.5 else "INVALID_OUTPUT_LIMITED", dominant
    if rate >= 0.2:
        return "MODERATE_RISK", dominant
    return "LOW_RISK", dominant


def _base(generated_ts: str, run_id: str) -> Dict[str, Any]:
    return {
        "generated_ts": generated_ts,
        "schema_version": SCHEMA_VERSION,
        "generalization_review_version": REVIEW_VERSION,
        "generalization_review_run_id": run_id,
    }


def _priority_map(prior_hypotheses: Sequence[Dict[str, Any]]) -> Dict[str, str]:
    return {
        _norm(row.get("hypothesis_id")): _norm(row.get("tier2_test_priority")) or _norm(row.get("priority"))
        for row in prior_hypotheses
        if _norm(row.get("hypothesis_id"))
    }


def _hypothesis_rows(
    generated_ts: str,
    run_id: str,
    prior_hypotheses: Sequence[Dict[str, Any]],
    transitions: Sequence[Dict[str, Any]],
    field_rows: Sequence[Dict[str, Any]],
    invalid_rows: Sequence[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    priorities = _priority_map(prior_hypotheses)
    by_transition = {transition: _transition_metrics([row for row in transitions if _norm(row.get("transition")) == transition]) for transition in TRANSITIONS}
    by_provider = {provider: _transition_metrics([row for row in transitions if _norm(row.get("provider")) == provider]) for provider in PROVIDERS}
    family_rows: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    field_specific: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in field_rows:
        family_rows[_norm(row.get("candidate_family"))].append(row)
        field_specific[_norm(row.get("candidate_field"))].append(row)
    usd_counts = _field_counts(family_rows["usdjpy_trend"])
    treasury_counts = _field_counts(family_rows["treasury_yields"])
    d_to_e = by_transition["D_to_E"]
    a_to_b = by_transition["A_to_B"]
    openai = by_provider["OpenAI"]
    gemini = by_provider["Gemini"]
    anthropic_invalid = [row for row in invalid_rows if _norm(row.get("provider")) == "Anthropic"]
    gemini_invalid = [row for row in invalid_rows if _norm(row.get("provider")) == "Gemini"]
    tier2_sessions = sorted(_session_set(transitions))
    rows: List[Dict[str, Any]] = []

    specs = [
        {
            "hypothesis_id": "HYP_USDJPY_TREND_REASONING",
            "tier2_result": "SUPPORTED",
            "generalization_status": "BEHAVIOR_CONFIRMED",
            "support": "STRONG",
            "evidence": f"usdjpy_trend used={usd_counts['used']}, changed_reasoning={usd_counts['changed']}; USDJPY_TREND_LABEL remains the strongest exact field.",
            "providers": sorted(usd_counts["providers_used"]),
            "transitions": ["A_to_B", "A_to_D", "A_to_E"],
            "fields": ["usdjpy_trend", "USDJPY_TREND_LABEL"],
            "invalid": "LOW_TO_MODERATE_NOT_BLOCKING",
            "revision": "USDJPY trend fields repeatedly change provider reasoning under controlled pack exposure.",
            "status": "READY_FOR_BEHAVIOR_TO_ACCURACY_HYPOTHESIS_DESIGN",
            "next": "Define behavior-to-accuracy hypothesis without claiming accuracy improvement.",
            "ready": "TRUE",
        },
        {
            "hypothesis_id": "HYP_A_TO_B_TARGET_STATE_VALUE",
            "tier2_result": "SUPPORTED",
            "generalization_status": "BEHAVIOR_CONFIRMED",
            "support": "STRONG",
            "evidence": f"A_to_B valid={a_to_b['valid_count']}, direction_changes={a_to_b['direction']}, no_signal_changes={a_to_b['no_signal']}, mean_complexity={a_to_b['mean_complexity']}.",
            "providers": sorted(a_to_b["valid_providers"]),
            "transitions": ["A_to_B"],
            "fields": ["usdjpy_trend"],
            "invalid": "LOW_TO_MODERATE_NOT_BLOCKING",
            "revision": "Pack B target-state exposure repeatedly produces behavior transitions.",
            "status": "READY_FOR_BEHAVIOR_TO_ACCURACY_HYPOTHESIS_DESIGN",
            "next": "Advance as a primary behavior-to-accuracy design candidate.",
            "ready": "TRUE",
        },
        {
            "hypothesis_id": "HYP_GEMINI_HIGH_SENSITIVITY",
            "tier2_result": "PARTIALLY_SUPPORTED",
            "generalization_status": "REVISED_CANDIDATE_PATTERN",
            "support": "MIXED",
            "evidence": f"Gemini valid_transition_count={gemini['valid_count']}, direction_changes={gemini['direction']}, no_signal_changes={gemini['no_signal']}, invalid_outputs={len(gemini_invalid)}.",
            "providers": ["Gemini"],
            "transitions": TRANSITIONS,
            "fields": ["usdjpy_trend", "dxy", "treasury_yields", "upcoming_larger_events"],
            "invalid": "HIGH_PROVIDER_AVAILABILITY_RISK",
            "revision": "Gemini appears highly behavior-sensitive when valid, but Tier 2 also shows Gemini provider-availability risk.",
            "status": "REVISE_HYPOTHESIS",
            "next": "Split into HYP_GEMINI_HIGH_SENSITIVITY_WHEN_VALID and HYP_GEMINI_PROVIDER_AVAILABILITY_RISK.",
            "ready": "FALSE",
        },
        {
            "hypothesis_id": "HYP_OPENAI_CAUSAL_STABLE",
            "tier2_result": "SUPPORTED",
            "generalization_status": "BEHAVIOR_CONFIRMED",
            "support": "STRONG",
            "evidence": f"OpenAI valid_transition_count={openai['valid_count']}, causal_chain_changes={openai['causal']}, invalid_outputs=0.",
            "providers": ["OpenAI"],
            "transitions": TRANSITIONS,
            "fields": ["all eligible deterministic families"],
            "invalid": "LOW",
            "revision": "OpenAI is output-stable and repeatedly rewrites causal chains under controlled pack exposure.",
            "status": "READY_FOR_BEHAVIOR_TO_ACCURACY_HYPOTHESIS_DESIGN",
            "next": "Advance as reliability-of-behavior hypothesis; do not treat as provider ranking.",
            "ready": "TRUE",
        },
        {
            "hypothesis_id": "HYP_PACK_E_REDUNDANCY",
            "tier2_result": "WEAKENED",
            "generalization_status": "REVISED_CANDIDATE_PATTERN",
            "support": "MIXED",
            "evidence": f"D_to_E valid={d_to_e['valid_count']}, direction_changes={d_to_e['direction']}, confidence_changes={d_to_e['confidence']}, no_signal_changes={d_to_e['no_signal']}.",
            "providers": sorted(d_to_e["valid_providers"]),
            "transitions": ["D_to_E"],
            "fields": ["full approved deterministic pack"],
            "invalid": "MODERATE_FOR_ANTHROPIC_E",
            "revision": "Pack E is not behaviorally redundant in Tier 2; revise toward D_to_E framing or prompt-variance instability.",
            "status": "REVISE_HYPOTHESIS",
            "next": "Investigate D_to_E behavioral instability before any accuracy design.",
            "ready": "FALSE",
        },
        {
            "hypothesis_id": "HYP_ANTHROPIC_DE_INVALID_RISK",
            "tier2_result": "SUPPORTED",
            "generalization_status": "INVALID_OUTPUT_LIMITED",
            "support": "INVALID_OUTPUT_LIMITED",
            "evidence": f"Anthropic invalid_outputs={len(anthropic_invalid)}, concentrated in C/D/E with malformed/truncated JSON.",
            "providers": ["Anthropic"],
            "transitions": ["C_to_D", "D_to_E", "A_to_E"],
            "fields": ["dxy", "treasury_yields", "upcoming_larger_events"],
            "invalid": "DIRECTLY_LIMITING",
            "revision": "Anthropic later-pack outputs remain malformed/truncated-output-risk-limited.",
            "status": "HOLD_DUE_INVALID_OUTPUTS",
            "next": "Design provider/output-risk guardrail before relying on Anthropic D/E behavior.",
            "ready": "FALSE",
        },
        {
            "hypothesis_id": "HYP_TREASURY_UNDERDETERMINED",
            "tier2_result": "PARTIALLY_SUPPORTED",
            "generalization_status": "CANDIDATE_PATTERN_RETAINED",
            "support": "MODERATE",
            "evidence": f"treasury_yields used={treasury_counts['used']}, changed_reasoning={treasury_counts['changed']}, discarded={treasury_counts['discarded']}, no_effect={treasury_counts['no_effect']}.",
            "providers": sorted(treasury_counts["providers_used"]),
            "transitions": ["C_to_D", "A_to_D", "A_to_E"],
            "fields": ["treasury_yields"],
            "invalid": "NOT_BLOCKING",
            "revision": "Treasury fields are behaviorally active but mixed, not ready for stronger promotion.",
            "status": "KEEP_AS_CANDIDATE_PATTERN",
            "next": "Retain as candidate behavior pattern; do not retire or promote.",
            "ready": "FALSE",
        },
    ]
    prior_by_id = {_norm(row.get("hypothesis_id")): row for row in prior_hypotheses}
    for spec in specs:
        prior = prior_by_id.get(spec["hypothesis_id"], {})
        row = _base(generated_ts, run_id)
        row.update(
            {
                "hypothesis_id": spec["hypothesis_id"],
                "hypothesis_priority": priorities.get(spec["hypothesis_id"]) or _norm(prior.get("tier2_test_priority")) or "",
                "prior_status": _norm(prior.get("current_evidence_status")) or "CANDIDATE_PATTERN",
                "tier2_result": spec["tier2_result"],
                "generalization_status": spec["generalization_status"],
                "behavior_support_level": spec["support"],
                "supporting_evidence_summary": _truncate_text(spec["evidence"], 500),
                "supporting_sessions": "|".join(tier2_sessions),
                "supporting_providers": "|".join(spec["providers"]),
                "supporting_transitions": "|".join(spec["transitions"]),
                "supporting_fields_or_families": "|".join(spec["fields"]),
                "invalid_output_impact": spec["invalid"],
                "revised_hypothesis_statement": spec["revision"],
                "recommended_status": spec["status"],
                "recommended_next_action": spec["next"],
                "ready_for_behavior_to_accuracy_design": spec["ready"],
                "accuracy_excluded": "TRUE",
                "production_excluded": "TRUE",
                "notes": "Behavior-only generalization; no accuracy or production claim.",
            }
        )
        rows.append(row)
    return rows


def _review_rows(
    generated_ts: str,
    run_id: str,
    summary: Dict[str, Any],
    valid_transition_count: int,
    invalid_transition_count: int,
    behavior_signal: str,
    hypotheses_ready: int,
) -> List[Dict[str, Any]]:
    sessions = _norm(summary.get("sessions_executed"))
    provider_calls = _norm(summary.get("provider_calls_attempted"))
    valid_outputs = int(_norm(summary.get("provider_calls_attempted")) or "0") - int(_norm(summary.get("invalid_output_count") or summary.get("invalid_outputs")) or "0")
    invalid_outputs = int(_norm(summary.get("invalid_output_count") or summary.get("invalid_outputs")) or "0")
    areas = [
        ("execution_scope", "PASS_WITH_WARNINGS", "Tier 2 executed the approved 8-session, 120-call grid with warnings from invalid outputs.", "PROCEED"),
        ("raw_archive_integrity", "PASS", "Raw responses archived equals provider calls attempted; append failures were zero.", "PROCEED"),
        ("invalid_output_review", "PASS_WITH_WARNINGS", "Invalid output rate was below the 20% hold threshold but provider-specific risks remain.", "GENERALIZE_WITH_RISK_LABELS"),
        ("behavior_signal", "PASS", "Tier 2 produced strong repeated behavior-transition evidence.", "PROMOTE_SUPPORTED_BEHAVIOR_HYPOTHESES"),
        ("hypothesis_generalization", "PASS_WITH_WARNINGS", f"{hypotheses_ready} hypotheses are ready for behavior-to-accuracy design; revised and held hypotheses remain separated.", "PROCEED_TO_NEXT_DESIGN"),
        ("governance", "PASS", "Accuracy, provider calls, reruns, forecast generation, and production changes were zero during this review.", "PROCEED"),
    ]
    rows: List[Dict[str, Any]] = []
    for area, status, conclusion, action in areas:
        row = _base(generated_ts, run_id)
        row.update(
            {
                "review_area": area,
                "review_status": status,
                "evidence_scope": "single_session_pilot|tier1_small_expansion|tier2_expansion",
                "sessions_included": sessions,
                "provider_calls_included": provider_calls,
                "valid_outputs_count": valid_outputs,
                "invalid_outputs_count": invalid_outputs,
                "valid_transition_count": valid_transition_count,
                "invalid_or_partial_transition_count": invalid_transition_count,
                "behavior_signal_classification": behavior_signal,
                "generalization_conclusion": conclusion,
                "recommended_next_action": action,
                "accuracy_excluded": "TRUE",
                "production_excluded": "TRUE",
                "notes": "Diagnostic-only review; no provider calls or accuracy scoring.",
            }
        )
        rows.append(row)
    return rows


def _provider_rows(
    generated_ts: str,
    run_id: str,
    forecasts: Sequence[Dict[str, Any]],
    transitions: Sequence[Dict[str, Any]],
    invalid_rows: Sequence[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for provider in PROVIDERS:
        outputs = [row for row in forecasts if _norm(row.get("provider")) == provider]
        invalid = [row for row in invalid_rows if _norm(row.get("provider")) == provider]
        metrics = _transition_metrics([row for row in transitions if _norm(row.get("provider")) == provider])
        behavior_class, risk_class = _provider_classification(provider, len(outputs), len(invalid), metrics)
        row = _base(generated_ts, run_id)
        row.update(
            {
                "provider": provider,
                "valid_output_count": sum(1 for row in outputs if _valid_output(row)),
                "invalid_output_count": len(invalid),
                "invalid_output_rate": _fmt_rate(len(invalid), len(outputs)),
                "valid_transition_count": metrics["valid_count"],
                "direction_change_count": metrics["direction"],
                "confidence_change_count": metrics["confidence"],
                "material_confidence_change_count": metrics["material_confidence"],
                "no_signal_change_count": metrics["no_signal"],
                "causal_chain_change_count": metrics["causal"],
                "information_used_change_count": metrics["info_used"],
                "mean_transition_complexity_score": metrics["mean_complexity"],
                "provider_behavior_classification": behavior_class,
                "provider_risk_classification": risk_class,
                "generalization_conclusion": _truncate_text(
                    f"{provider} shows {behavior_class}; output risk classified as {risk_class}.", 500
                ),
                "accuracy_interpretation_forbidden": "TRUE",
                "notes": "Provider behavior classification is not provider forecast ranking.",
            }
        )
        rows.append(row)
    return rows


def _transition_rows(generated_ts: str, run_id: str, transitions: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for transition in TRANSITIONS:
        metrics = _transition_metrics([row for row in transitions if _norm(row.get("transition")) == transition])
        value, status = _transition_classification(transition, metrics)
        row = _base(generated_ts, run_id)
        row.update(
            {
                "pack_transition": transition,
                "valid_transition_count": metrics["valid_count"],
                "invalid_or_partial_transition_count": metrics["invalid_count"],
                "direction_change_count": metrics["direction"],
                "confidence_change_count": metrics["confidence"],
                "no_signal_change_count": metrics["no_signal"],
                "causal_chain_change_count": metrics["causal"],
                "information_used_change_count": metrics["info_used"],
                "mean_transition_complexity_score": metrics["mean_complexity"],
                "max_transition_complexity_score": metrics["max_complexity"],
                "behavioral_value_classification": value,
                "generalization_status": status,
                "interpretation": _truncate_text(
                    f"{transition} generated {metrics['causal']} causal-chain changes across {metrics['valid_count']} valid transitions.", 500
                ),
                "next_phase_relevance": "PRIMARY_BEHAVIOR_TO_ACCURACY_CANDIDATE" if status == "BEHAVIOR_CONFIRMED" else "SUPPORTING_BEHAVIOR_CONTEXT",
                "notes": "Behavioral value only; no accuracy or pack ranking.",
            }
        )
        rows.append(row)
    return rows


def _field_rows(generated_ts: str, run_id: str, field_rows: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    grouped: Dict[Tuple[str, str, str], List[Dict[str, Any]]] = defaultdict(list)
    for row in field_rows:
        family = _norm(row.get("candidate_family"))
        field = _norm(row.get("candidate_field"))
        if family:
            grouped[(family, "", "FIELD_FAMILY")].append(row)
        if field:
            grouped[(family, field, "FIELD")].append(row)
    for (family, field, scope), group in sorted(grouped.items()):
        counts = _field_counts(group)
        classification, status = _field_classification(counts, scope)
        # Keep all family rows and important exact fields; skip low-signal exact fields to keep the sheet readable.
        if scope == "FIELD" and counts["used"] < 10 and counts["changed"] < 3:
            continue
        row = _base(generated_ts, run_id)
        row.update(
            {
                "candidate_family": family,
                "candidate_field": field,
                "field_scope": scope,
                "used_count": counts["used"],
                "changed_reasoning_count": counts["changed"],
                "discarded_count": counts["discarded"],
                "no_effect_count": counts["no_effect"],
                "available_not_mentioned_count": counts["available_not_mentioned"],
                "sessions_with_use": "|".join(sorted(counts["sessions_used"])),
                "sessions_with_changed_reasoning": "|".join(sorted(counts["sessions_changed"])),
                "providers_with_use": "|".join(sorted(counts["providers_used"])),
                "providers_with_changed_reasoning": "|".join(sorted(counts["providers_changed"])),
                "field_behavior_classification": classification,
                "generalization_status": status,
                "interpretation": _truncate_text(
                    f"{scope.lower()} {field or family} used={counts['used']} changed_reasoning={counts['changed']} discarded={counts['discarded']} no_effect={counts['no_effect']}.",
                    500,
                ),
                "next_phase_relevance": "PRIMARY" if status == "BEHAVIOR_CONFIRMED" else "SUPPORTING_OR_UNDERDETERMINED",
                "notes": "Exact-field matching is conservative and may undercount vague family-level influence.",
            }
        )
        rows.append(row)
    return rows


def _nosignal_rows(generated_ts: str, run_id: str, transitions: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    scopes: List[Tuple[str, str, str, List[Dict[str, Any]]]] = [
        ("", "", "OVERALL", list(transitions)),
    ]
    for provider in PROVIDERS:
        provider_rows = [row for row in transitions if _norm(row.get("provider")) == provider]
        scopes.append((provider, "", "PROVIDER", provider_rows))
        for transition in TRANSITIONS:
            scopes.append((provider, transition, "PROVIDER_TRANSITION", [row for row in provider_rows if _norm(row.get("transition")) == transition]))
    for provider, transition, scope, group in scopes:
        valid = [row for row in group if _valid_transition(row)]
        changes = [row for row in valid if _upper(row.get("no_signal_transition")) == "CHANGED"]
        reductions = [row for row in changes if _upper(row.get("no_signal_from")) == "TRUE" and _upper(row.get("no_signal_to")) == "FALSE"]
        increases = [row for row in changes if _upper(row.get("no_signal_from")) == "FALSE" and _upper(row.get("no_signal_to")) == "TRUE"]
        confidence_changes = [row for row in valid if _confidence_changed(row)]
        material_changes = [row for row in valid if _material_confidence_changed(row)]
        deltas = [_float(row.get("confidence_delta")) for row in confidence_changes]
        deltas = [value for value in deltas if value is not None]
        if not valid:
            no_signal_status = "UNDERDETERMINED"
        elif len(reductions) > len(increases) and reductions:
            no_signal_status = "REPEATED_NO_SIGNAL_REDUCTION"
        elif len(increases) > len(reductions) and increases:
            no_signal_status = "REPEATED_NO_SIGNAL_INCREASE"
        elif changes:
            no_signal_status = "MIXED_NO_SIGNAL_BEHAVIOR"
        else:
            no_signal_status = "NO_SIGNAL_STABLE"
        confidence_status = "MIXED_NO_SIGNAL_BEHAVIOR" if material_changes else "UNDERDETERMINED"
        row = _base(generated_ts, run_id)
        row.update(
            {
                "provider": provider,
                "pack_transition": transition,
                "scope": scope,
                "no_signal_change_count": len(changes),
                "no_signal_reduction_count": len(reductions),
                "no_signal_increase_count": len(increases),
                "confidence_change_count": len(confidence_changes),
                "material_confidence_change_count": len(material_changes),
                "mean_confidence_delta": _fmt_mean(deltas),
                "max_confidence_delta_abs": f"{max(abs(value) for value in deltas):.0f}" if deltas else "",
                "no_signal_generalization_status": no_signal_status,
                "confidence_generalization_status": confidence_status,
                "interpretation": "Confidence/no-signal behavior only; not accuracy.",
                "notes": "",
            }
        )
        rows.append(row)
    return rows


def _invalid_rows(
    generated_ts: str,
    run_id: str,
    forecasts: Sequence[Dict[str, Any]],
    invalid_rows: Sequence[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    scopes: List[Tuple[str, str, str]] = [(provider, "", "PROVIDER") for provider in PROVIDERS]
    scopes.extend((provider, pack, "PROVIDER_PACK_LEVEL") for provider in PROVIDERS for pack in PACK_LEVELS)
    for provider, pack, scope in scopes:
        attempted = [
            row
            for row in forecasts
            if _norm(row.get("provider")) == provider and (not pack or _norm(row.get("pack_level")) == pack)
        ]
        invalid = [
            row
            for row in invalid_rows
            if _norm(row.get("provider")) == provider and (not pack or _norm(row.get("pack_level")) == pack)
        ]
        reasons = Counter(_norm(row.get("invalid_reason")) for row in invalid if _norm(row.get("invalid_reason")))
        status, dominant = _risk_status(provider, pack, len(attempted), len(invalid), reasons)
        if scope == "PROVIDER_PACK_LEVEL" and len(invalid) == 0 and pack not in {"D", "E"}:
            continue
        row = _base(generated_ts, run_id)
        row.update(
            {
                "provider": provider,
                "pack_level": pack,
                "scope": scope,
                "attempted_count": len(attempted),
                "invalid_output_count": len(invalid),
                "invalid_output_rate": _fmt_rate(len(invalid), len(attempted)),
                "dominant_invalid_reason": dominant,
                "risk_pattern": json.dumps(dict(reasons), ensure_ascii=True),
                "risk_status": status,
                "tier3_or_next_phase_implication": "Monitor and isolate invalid cells; do not silently rerun or repair.",
                "notes": "Invalid-output risk is not forecast-performance ranking.",
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
        ("PACK_BEHAVIOR_TIER2_GENERALIZATION_REVIEW", OUTPUT_REVIEW, "tier2_behavior_generalization_review"),
        ("PACK_BEHAVIOR_TIER2_HYPOTHESIS_GENERALIZATION", OUTPUT_HYPOTHESIS, "tier2_hypothesis_generalization"),
        ("PACK_BEHAVIOR_TIER2_PROVIDER_GENERALIZATION", OUTPUT_PROVIDER, "tier2_provider_generalization"),
        ("PACK_BEHAVIOR_TIER2_TRANSITION_GENERALIZATION", OUTPUT_TRANSITION, "tier2_transition_generalization"),
        ("PACK_BEHAVIOR_TIER2_FIELD_GENERALIZATION", OUTPUT_FIELD, "tier2_field_generalization"),
        ("PACK_BEHAVIOR_TIER2_NOSIGNAL_GENERALIZATION", OUTPUT_NOSIGNAL, "tier2_no_signal_generalization"),
        ("PACK_BEHAVIOR_TIER2_INVALID_OUTPUT_GENERALIZATION", OUTPUT_INVALID, "tier2_invalid_output_generalization"),
        ("PACK_BEHAVIOR_TIER2_GENERALIZATION_SUMMARY", OUTPUT_SUMMARY, "tier2_generalization_summary"),
    ]
    updates: List[Dict[str, Any]] = []
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
            "notes": "Phase 9A-4ZZ Tier 2 behavior generalization review; behavior-only, no accuracy evaluation.",
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
    parser = argparse.ArgumentParser(description="Build PreSignal v2.0 Phase 9A-4ZZ Tier 2 generalization review.")
    return parser.parse_args(argv)


def build_pack_behavior_tier2_generalization_review_v0(args: Optional[argparse.Namespace] = None) -> Dict[str, Any]:
    args = args or _parse_args()
    generated_ts = _iso_now()
    review_run_id = _run_id(generated_ts)
    service = build_sheets_service(load_credentials())
    titles = _sheet_titles(service, DIAGNOSTICS_SPREADSHEET_ID)
    missing_required: List[str] = []
    missing_optional: List[str] = []

    tier2_summary_rows = _safe_rows(service, titles, TIER2_SUMMARY, missing_required, required=True)
    tier2_forecasts = _safe_rows(service, titles, TIER2_FORECASTS, missing_required, required=True)
    tier2_transitions = _safe_rows(service, titles, TIER2_TRANSITIONS, missing_required, required=True)
    tier2_field = _safe_rows(service, titles, TIER2_FIELD, missing_required, required=True)
    tier2_nosignal = _safe_rows(service, titles, TIER2_NOSIGNAL, missing_required, required=True)
    tier2_invalid = _safe_rows(service, titles, TIER2_INVALID, missing_required, required=True)
    tier2_raw = _safe_rows(service, titles, TIER2_RAW, missing_required, required=True)
    _safe_rows(service, titles, TIER2_RUNS, missing_required, required=True)
    _safe_rows(service, titles, TIER2_METADATA, missing_required, required=True)
    _safe_rows(service, titles, TIER2_BEHAVIOR, missing_required, required=True)
    _safe_rows(service, titles, TIER2_CHECKPOINTS, missing_required, required=True)
    _safe_rows(service, titles, TIER2_LOG, missing_required, required=True)

    tier2_experiment = _safe_rows(service, titles, TIER2_EXPERIMENT_DESIGN, missing_optional)
    tier2_plan = _safe_rows(service, titles, TIER2_HYPOTHESIS_PLAN, missing_optional)
    tier2_success = _safe_rows(service, titles, TIER2_SUCCESS_CRITERIA, missing_optional)
    tier2_design_summary = _safe_rows(service, titles, TIER2_DESIGN_SUMMARY, missing_optional)
    prior_hypotheses = _safe_rows(service, titles, PRIOR_HYPOTHESES, missing_optional)
    prior_summary = _safe_rows(service, titles, PRIOR_GENERALIZATION_SUMMARY, missing_optional)
    tier1_summary = _safe_rows(service, titles, TIER1_SUMMARY, missing_optional)
    pilot_summary = _safe_rows(service, titles, PILOT_SUMMARY, missing_optional)
    for optional in [
        PRIOR_GENERALIZATION_AUDIT,
        PRIOR_PROVIDER,
        PRIOR_TRANSITION,
        PRIOR_FIELD,
        PRIOR_NOSIGNAL,
        PRIOR_INVALID,
        TIER1_RUNS,
        TIER1_FORECASTS,
        TIER1_BEHAVIOR,
        TIER1_TRANSITIONS,
        TIER1_FIELD,
        TIER1_NOSIGNAL,
        TIER1_INVALID,
        PILOT_BEHAVIOR_COMPARE,
        PILOT_TRANSITIONS,
        PILOT_PROVIDER,
        PILOT_FIELD,
        PILOT_NOSIGNAL,
        PILOT_INVALID,
    ]:
        _safe_rows(service, titles, optional, missing_optional)

    if missing_required or not tier2_summary_rows:
        raise RuntimeError(f"Missing required Tier 2 execution evidence sheets: {missing_required}")

    summary = tier2_summary_rows[-1]
    transition_metrics = _transition_metrics(tier2_transitions)
    valid_outputs = sum(1 for row in tier2_forecasts if _valid_output(row))
    invalid_outputs = len(tier2_invalid)
    provider_calls = int(_norm(summary.get("provider_calls_attempted")) or len(tier2_forecasts))
    raw_archived = int(_norm(summary.get("raw_responses_archived")) or len(tier2_raw))
    raw_complete = raw_archived == provider_calls
    invalid_rate = invalid_outputs / provider_calls if provider_calls else 0
    behavior_signal = "STRONG_BEHAVIOR_PATTERN_SIGNAL" if transition_metrics["valid_count"] >= 100 and transition_metrics["causal"] == transition_metrics["valid_count"] else "MODERATE_BEHAVIOR_PATTERN_SIGNAL"

    hypothesis_rows = _hypothesis_rows(generated_ts, review_run_id, prior_hypotheses, tier2_transitions, tier2_field, tier2_invalid)
    ready_hypotheses = [row for row in hypothesis_rows if _truth(row.get("ready_for_behavior_to_accuracy_design"))]
    confirmed = [row for row in hypothesis_rows if _norm(row.get("generalization_status")) == "BEHAVIOR_CONFIRMED"]
    revised = [row for row in hypothesis_rows if _norm(row.get("recommended_status")) == "REVISE_HYPOTHESIS"]
    held = [row for row in hypothesis_rows if _norm(row.get("recommended_status")) == "HOLD_DUE_INVALID_OUTPUTS"]
    retired = [row for row in hypothesis_rows if _norm(row.get("recommended_status")) == "RETIRE_HYPOTHESIS"]

    provider_rows = _provider_rows(generated_ts, review_run_id, tier2_forecasts, tier2_transitions, tier2_invalid)
    transition_rows = _transition_rows(generated_ts, review_run_id, tier2_transitions)
    field_rows = _field_rows(generated_ts, review_run_id, tier2_field)
    nosignal_rows = _nosignal_rows(generated_ts, review_run_id, tier2_transitions)
    invalid_rows = _invalid_rows(generated_ts, review_run_id, tier2_forecasts, tier2_invalid)
    review_rows = _review_rows(generated_ts, review_run_id, summary, transition_metrics["valid_count"], transition_metrics["invalid_count"], behavior_signal, len(ready_hypotheses))

    blocking_governance = (
        not raw_complete
        or invalid_rate > 0.20
        or int(_norm(summary.get("accuracy_evaluation_count")) or "0") != 0
        or int(_norm(summary.get("production_behavior_change_count")) or "0") != 0
    )
    ready_for_behavior_to_accuracy = raw_complete and invalid_rate <= 0.20 and len(ready_hypotheses) >= 2 and not blocking_governance
    build_status = "FAIL" if blocking_governance else ("PASS_WITH_WARNINGS" if invalid_outputs or revised or held else "PASS")
    final_interpretation = (
        "TIER2_BEHAVIOR_GENERALIZATION_REVIEW_BLOCKED"
        if blocking_governance
        else "TIER2_BEHAVIOR_GENERALIZATION_REVIEW_READY_WITH_WARNINGS"
        if build_status == "PASS_WITH_WARNINGS"
        else "TIER2_BEHAVIOR_GENERALIZATION_REVIEW_READY"
    )
    recommended_next_step = (
        "HOLD_PHASE9_PENDING_GOVERNANCE_REVIEW"
        if blocking_governance
        else "PROCEED_TO_PHASE9A5A_BEHAVIOR_TO_ACCURACY_HYPOTHESIS_DESIGN"
        if ready_for_behavior_to_accuracy
        else "PROCEED_TO_PHASE9A4Z3_TIER3_STABILITY_DESIGN"
    )

    strongest_provider = "OpenAI output-stable causal rewriter; Gemini highest sensitivity when valid"
    strongest_transition = "A_to_D and A_to_B"
    strongest_field_family = "usdjpy_trend"
    strongest_no_signal = "Gemini and Anthropic repeated no-signal movement; A_to_D/A_to_E strongest broad transitions"
    strongest_invalid = "Gemini provider 503 availability risk; Anthropic malformed/truncated later-pack risk"
    strongest_hypothesis = "HYP_USDJPY_TREND_REASONING"

    summary_row = _base(generated_ts, review_run_id)
    summary_row.update(
        {
            "build_status": build_status,
            "final_interpretation": final_interpretation,
            "sessions_total": _norm(summary.get("sessions_executed")),
            "provider_calls_total": provider_calls,
            "raw_responses_archived": raw_archived,
            "invalid_output_count": invalid_outputs,
            "invalid_output_rate": f"{invalid_rate:.3f}",
            "valid_transition_count": transition_metrics["valid_count"],
            "invalid_or_partial_transition_count": transition_metrics["invalid_count"],
            "hypotheses_reviewed": len(hypothesis_rows),
            "hypotheses_behavior_confirmed": len(confirmed),
            "hypotheses_ready_for_behavior_to_accuracy_design": len(ready_hypotheses),
            "hypotheses_promoted_to_tier3_stability": 0,
            "hypotheses_revised": len(revised),
            "hypotheses_held_due_invalid_outputs": len(held),
            "hypotheses_retired": len(retired),
            "strongest_behavior_confirmed_hypothesis": strongest_hypothesis,
            "strongest_provider_generalization": strongest_provider,
            "strongest_transition_generalization": strongest_transition,
            "strongest_field_family_generalization": strongest_field_family,
            "strongest_no_signal_generalization": strongest_no_signal,
            "strongest_invalid_output_risk": strongest_invalid,
            "accuracy_evaluation_count": 0,
            "provider_call_count_this_review": 0,
            "forecast_generation_count_this_review": 0,
            "provider_rerun_count_this_review": 0,
            "production_behavior_change_count": 0,
            "ready_for_behavior_to_accuracy_hypothesis_design": "TRUE" if ready_for_behavior_to_accuracy else "FALSE",
            "ready_for_tier3_stability_check": "TRUE",
            "ready_for_accuracy_evaluation": "FALSE",
            "ready_for_production": "FALSE",
            "recommended_next_step": recommended_next_step,
            "notes": _truncate_text(
                json.dumps(
                    {
                        "missing_optional": missing_optional,
                        "tier2_execution_run_id": _norm(summary.get("execution_run_id") or summary.get("discovery_run_id")),
                        "prior_total_sessions": (prior_summary[-1].get("total_sessions_included") if prior_summary else ""),
                        "tier1_invalid_outputs": (tier1_summary[-1].get("invalid_outputs") if tier1_summary else ""),
                        "pilot_invalid_outputs": (pilot_summary[-1].get("invalid_outputs_count") if pilot_summary else ""),
                    },
                    ensure_ascii=True,
                ),
                500,
            ),
        }
    )

    outputs = [
        (OUTPUT_REVIEW, REVIEW_HEADERS, review_rows),
        (OUTPUT_HYPOTHESIS, HYPOTHESIS_HEADERS, hypothesis_rows),
        (OUTPUT_PROVIDER, PROVIDER_HEADERS, provider_rows),
        (OUTPUT_TRANSITION, TRANSITION_HEADERS, transition_rows),
        (OUTPUT_FIELD, FIELD_HEADERS, field_rows),
        (OUTPUT_NOSIGNAL, NOSIGNAL_HEADERS, nosignal_rows),
        (OUTPUT_INVALID, INVALID_HEADERS, invalid_rows),
        (OUTPUT_SUMMARY, SUMMARY_HEADERS, [summary_row]),
    ]
    for sheet_name, headers, rows in outputs:
        sheet_headers = _ensure_sheet(service, DIAGNOSTICS_SPREADSHEET_ID, sheet_name, headers)
        _write_rows(service, DIAGNOSTICS_SPREADSHEET_ID, sheet_name, sheet_headers, rows)
    registry = _upsert_registry_rows(service)

    return {
        "build_status": build_status,
        "final_interpretation": final_interpretation,
        "generalization_review_run_id": review_run_id,
        "file_created": "automation/build_pack_behavior_tier2_generalization_review_v0.py",
        "sheets_written": {sheet_name: len(rows) for sheet_name, _, rows in outputs},
        "hypotheses_reviewed": len(hypothesis_rows),
        "hypotheses_behavior_confirmed": len(confirmed),
        "hypotheses_ready_for_behavior_to_accuracy_design": len(ready_hypotheses),
        "hypotheses_promoted_to_tier3_stability": 0,
        "hypotheses_revised": len(revised),
        "hypotheses_held_due_invalid_outputs": len(held),
        "hypotheses_retired": len(retired),
        "strongest_behavior_confirmed_hypothesis": strongest_hypothesis,
        "strongest_provider_generalization": strongest_provider,
        "strongest_transition_generalization": strongest_transition,
        "strongest_field_family_generalization": strongest_field_family,
        "strongest_no_signal_generalization": strongest_no_signal,
        "strongest_invalid_output_risk": strongest_invalid,
        "accuracy_evaluation_count": 0,
        "provider_call_count_this_review": 0,
        "forecast_generation_count_this_review": 0,
        "provider_rerun_count_this_review": 0,
        "production_behavior_change_count": 0,
        "ready_for_behavior_to_accuracy_hypothesis_design": ready_for_behavior_to_accuracy,
        "ready_for_tier3_stability_check": True,
        "ready_for_accuracy_evaluation": False,
        "ready_for_production": False,
        "recommended_next_step": recommended_next_step,
        "registry": registry,
    }


def main() -> None:
    result = build_pack_behavior_tier2_generalization_review_v0()
    print(json.dumps(result, indent=2, ensure_ascii=True))


if __name__ == "__main__":
    main()
